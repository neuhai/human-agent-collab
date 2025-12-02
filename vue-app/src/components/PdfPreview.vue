<template>
  <div class="pdf-viewer-container" v-if="visible">
    <div v-if="loading" class="pdf-loading">Loading PDF...</div>
    <div v-else-if="error" class="pdf-error">
      <p><strong>Error loading PDF:</strong> {{ error }}</p>
      <p class="pdf-error-helper">Falling back to text content...</p>
    </div>
    <div
      v-else
      id="pdf-viewer-wrapper"
      class="pdf-wrapper"
      :style="{ display: pageCount > 0 ? 'block' : 'none' }"
    >
      <div
        v-for="pageNum in pageCount"
        :key="pageNum"
        class="pdf-page-container"
      >
        <canvas
          :ref="el => setCanvasRef(el, pageNum)"
          :class="['pdf-canvas', `pdf-page-${pageNum}`]"
        ></canvas>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'

export default defineComponent({
  name: 'PdfPreview',
  props: {
    fileUrl: {
      type: String,
      required: false,
      default: ''
    },
    visible: {
      type: Boolean,
      required: true
    }
  },
  emits: ['error'],
  setup(props, { emit }) {
    const loading = ref(false)
    const error = ref<string | null>(null)
    const pageCount = ref(0)
    const canvasRefs = ref<Map<number, HTMLCanvasElement>>(new Map())
    let pdfDocInstance: any = null

    const getPdfJsLib = (): any => {
      const win = window as any
      if (win['pdfjs-dist'] && win['pdfjs-dist']['build'] && win['pdfjs-dist']['build']['pdf']) {
        return win['pdfjs-dist']['build']['pdf']
      }
      if (win.pdfjsLib) return win.pdfjsLib
      if (win.pdfjs) return win.pdfjs
      if (win['pdfjs-dist/build/pdf']) return win['pdfjs-dist/build/pdf']
      return null
    }

    const setCanvasRef = (el: any, pageNum: number) => {
      if (el && el instanceof HTMLCanvasElement) {
        canvasRefs.value.set(pageNum, el)
      }
    }

    const resetState = () => {
      loading.value = false
      error.value = null
      pageCount.value = 0
      pdfDocInstance = null
      // Clear all canvases
      canvasRefs.value.forEach((canvas) => {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
        }
      })
      canvasRefs.value.clear()
    }

    const loadPdf = async () => {
      resetState()
      if (!props.visible || !props.fileUrl) {
        return
      }

      loading.value = true
      error.value = null

      try {
        let pdfjsLib = getPdfJsLib()
        let retries = 0
        while (!pdfjsLib && retries < 10) {
          await new Promise(resolve => setTimeout(resolve, 100))
          pdfjsLib = getPdfJsLib()
          retries++
        }

        if (!pdfjsLib) {
          throw new Error('PDF.js library not loaded. Please refresh the page.')
        }

        if (pdfjsLib.GlobalWorkerOptions) {
          pdfjsLib.GlobalWorkerOptions.workerSrc =
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'
        }

        const loadingTask = pdfjsLib.getDocument({
          url: props.fileUrl,
          withCredentials: false
        })

        const pdf = await loadingTask.promise
        if (!pdf || typeof pdf.getPage !== 'function') {
          throw new Error('Invalid PDF document loaded')
        }

        pdfDocInstance = pdf
        pageCount.value = pdf.numPages
        
        // Set loading to false so the canvas elements get rendered
        loading.value = false
        
        // Wait for Vue to update the DOM and render all canvas elements
        // Use multiple nextTick calls and requestAnimationFrame to ensure DOM is updated
        await nextTick()
        await nextTick()
        await new Promise(resolve => requestAnimationFrame(resolve))
        await new Promise(resolve => setTimeout(resolve, 100))

        // Wait for all canvases to be available in the DOM
        // Find canvases directly from DOM since refs might not be set yet
        let allCanvasesReady = false
        let attempts = 0
        const maxAttempts = 100 // Increased attempts
        
        while (!allCanvasesReady && attempts < maxAttempts) {
          const wrapper = document.getElementById('pdf-viewer-wrapper')
          if (!wrapper) {
            await nextTick()
            await new Promise(resolve => setTimeout(resolve, 50))
            attempts++
            continue
          }
          
          // Check if all canvases are available in DOM
          allCanvasesReady = true
          for (let pageNum = 1; pageNum <= pageCount.value; pageNum++) {
            // Try to find canvas in DOM by class name
            const canvas = wrapper.querySelector(`.pdf-page-${pageNum}`) as HTMLCanvasElement
            
            if (!canvas) {
              allCanvasesReady = false
              break
            }
            
            // Verify canvas is actually in the DOM
            if (!canvas.isConnected && !document.body.contains(canvas)) {
              allCanvasesReady = false
              break
            }
            
            // Store in refs map for later use
            canvasRefs.value.set(pageNum, canvas)
          }
          
          if (allCanvasesReady) {
            break
          }
          
          // Wait before retrying
          await nextTick()
          await new Promise(resolve => setTimeout(resolve, 50))
          await new Promise(resolve => requestAnimationFrame(resolve))
          attempts++
        }
        
        if (allCanvasesReady) {
          // Render all pages
          await renderAllPages()
        } else {
          // Try one more time with a longer wait
          await new Promise(resolve => setTimeout(resolve, 200))
          const wrapper = document.getElementById('pdf-viewer-wrapper')
          if (wrapper) {
            let foundAll = true
            for (let pageNum = 1; pageNum <= pageCount.value; pageNum++) {
              const canvas = wrapper.querySelector(`.pdf-page-${pageNum}`) as HTMLCanvasElement
              if (canvas) {
                canvasRefs.value.set(pageNum, canvas)
              } else {
                foundAll = false
                break
              }
            }
            if (foundAll) {
              await renderAllPages()
            } else {
              throw new Error(`Canvas elements not available for rendering. Found ${canvasRefs.value.size} of ${pageCount.value} canvases.`)
            }
          } else {
            throw new Error('PDF viewer wrapper not found in DOM')
          }
        }
      } catch (e: any) {
        console.error('PdfPreview: error loading PDF', e)
        const message = e?.message || 'Failed to load PDF'
        error.value = message
        loading.value = false
        pdfDocInstance = null
        pageCount.value = 0
        emit('error', message)
      }
    }

    const renderPage = async (pageNum: number) => {
      if (!pdfDocInstance) return
      try {
        if (typeof pdfDocInstance.getPage !== 'function') {
          throw new Error('PDF document is not properly initialized')
        }

        const page = await pdfDocInstance.getPage(pageNum)
        const scale = 1.5
        const viewport = page.getViewport({ scale })

        // Get canvas for this page - try multiple strategies
        let canvas = canvasRefs.value.get(pageNum)
        
        // If not in refs, try to find in DOM
        if (!canvas) {
          const wrapper = document.getElementById('pdf-viewer-wrapper')
          if (wrapper) {
            canvas = wrapper.querySelector(`.pdf-page-${pageNum}`) as HTMLCanvasElement
            if (canvas) {
              canvasRefs.value.set(pageNum, canvas)
            }
          }
        }
        
        // If still not found, try querySelectorAll and find by index
        if (!canvas) {
          const wrapper = document.getElementById('pdf-viewer-wrapper')
          if (wrapper) {
            const allCanvases = wrapper.querySelectorAll('canvas')
            if (allCanvases.length >= pageNum) {
              canvas = allCanvases[pageNum - 1] as HTMLCanvasElement
              if (canvas) {
                canvasRefs.value.set(pageNum, canvas)
              }
            }
          }
        }
        
        // Final check - wait a bit and retry if still not found
        if (!canvas) {
          await nextTick()
          await new Promise(resolve => setTimeout(resolve, 50))
          const wrapper = document.getElementById('pdf-viewer-wrapper')
          if (wrapper) {
            canvas = wrapper.querySelector(`.pdf-page-${pageNum}`) as HTMLCanvasElement
            if (!canvas) {
              // Try querySelectorAll as fallback
              const allCanvases = wrapper.querySelectorAll('canvas')
              if (allCanvases.length >= pageNum) {
                canvas = allCanvases[pageNum - 1] as HTMLCanvasElement
              }
            }
            if (canvas) {
              canvasRefs.value.set(pageNum, canvas)
            }
          }
        }
        
        if (!canvas) {
          throw new Error(`Canvas element for page ${pageNum} not available in DOM after retry`)
        }
        
        // Verify canvas is connected to DOM
        if (!canvas.isConnected && !document.body.contains(canvas)) {
          throw new Error(`Canvas element for page ${pageNum} is not connected to DOM`)
        }

        const context = canvas.getContext('2d')
        if (!context) {
          throw new Error('Failed to get canvas context')
        }

        // Set canvas dimensions before rendering
        canvas.height = viewport.height
        canvas.width = viewport.width
        context.clearRect(0, 0, canvas.width, canvas.height)

        const renderContext = { canvasContext: context, viewport }
        await page.render(renderContext).promise
      } catch (e: any) {
        console.error(`PdfPreview: error rendering page ${pageNum}`, e)
        error.value = e?.message || `Failed to render PDF page ${pageNum}`
        throw e
      }
    }

    const renderAllPages = async () => {
      if (!pdfDocInstance || pageCount.value === 0) return
      
      // Add a small delay to ensure all canvases are in the DOM
      await nextTick()
      await new Promise(resolve => setTimeout(resolve, 100))
      
      // Render all pages sequentially
      for (let pageNum = 1; pageNum <= pageCount.value; pageNum++) {
        try {
          await renderPage(pageNum)
          // Small delay between pages to avoid overwhelming the browser
          if (pageNum < pageCount.value) {
            await new Promise(resolve => setTimeout(resolve, 10))
          }
        } catch (e) {
          console.error(`Failed to render page ${pageNum}:`, e)
          // Continue rendering other pages even if one fails
        }
      }
    }

    // Watch for when pageCount changes and canvases become available
    watch(pageCount, async (newCount) => {
      if (newCount > 0 && pdfDocInstance) {
        // Wait for all canvases to be rendered
        try {
          await nextTick()
          await nextTick()
          await new Promise(resolve => requestAnimationFrame(resolve))
          
          // Check if all canvases are ready
          let allReady = true
          for (let pageNum = 1; pageNum <= newCount; pageNum++) {
            if (!canvasRefs.value.get(pageNum)) {
              allReady = false
              break
            }
          }
          
          if (allReady) {
            await renderAllPages()
          }
        } catch (e) {
          console.warn('Error rendering in pageCount watcher:', e)
        }
      }
    })

    watch(
      () => [props.fileUrl, props.visible],
      () => {
        if (props.visible && props.fileUrl) {
          loadPdf()
        } else {
          resetState()
        }
      }
    )

    onMounted(() => {
      if (props.visible && props.fileUrl) {
        loadPdf()
      }
    })

    onBeforeUnmount(() => {
      resetState()
    })

    return {
      loading,
      error,
      pageCount,
      setCanvasRef
    }
  }
})
</script>

<style scoped>
.pdf-viewer-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.pdf-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  overflow-y: auto;
  overflow-x: hidden;
  width: 100%;
  height: 100%;
  padding: 10px;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 #f1f5f9;
}

.pdf-wrapper::-webkit-scrollbar {
  width: 8px;
}

.pdf-wrapper::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

.pdf-wrapper::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.pdf-wrapper::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.pdf-page-container {
  display: flex;
  justify-content: center;
  width: 100%;
  margin-bottom: 10px;
}

.pdf-canvas {
  border: 1px solid #ddd;
  max-width: 100%;
  height: auto;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: block;
}

.pdf-loading {
  text-align: center;
  padding: 40px;
}

.pdf-error {
  color: #dc2626;
  padding: 20px;
  background: #fee2e2;
  border-radius: 4px;
  margin-bottom: 10px;
}

.pdf-error-helper {
  margin-top: 10px;
  font-size: 14px;
}
</style>


