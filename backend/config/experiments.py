# Experiment configurations
# This should match the frontend experiment configs

EXPERIMENTS = [
    {
        'id': 'shapefactory',
        'name': 'Shape Factory',
        'tags': ['Coordination', 'Trade'],
        'description': '**Procedures**: Each participant can produce shapes, buy&sell shapes, and chat with others. Each one is assigned a specialty shape that can be cheaply produced.\n\n**Constraints**: shape production limit; time limit.\n\n**Goal**: Maximize individual profit.',
        'params': [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Money": [
                    {'label': "Participant Initial Money ($)", 'type': "number", 'default': 200, 'path': 'Session.Params.startingMoney'},
                    {'label': "Regular Shape Production Cost ($)", 'type': "number", 'default': 40, 'path': 'Session.Params.regularCost'},
                    {'label': "Specialty Production Cost ($)", 'type': "number", 'default': 15, 'path': 'Session.Params.specialtyCost'},
                    {'label': "Min. Trade Price ($)", 'type': "number", 'default': 15, 'path': 'Session.Params.minTradePrice'},
                    {'label': "Max. Trade Price ($)", 'type': "number", 'default': 100, 'path': 'Session.Params.maxTradePrice'},
                    {'label': "Order Incentive ($/shape fulfilled)", 'type': "number", 'default': 60, 'path': 'Session.Params.incentiveMoney'}
                ],
                "Shape Production & Order": [
                    {'label': "Production Time (sec)", 'type': "number", 'default': 30, 'path': 'Session.Params.productionTime', 'description': "Time required to produce one shape."},
                    {'label': "# Max. Production", 'type': "number", 'default': 3, 'path': 'Session.Params.maxProductionNum', 'description': "Maximum total number of shapes a participant can produce (specialty and non-specialty combined)."},
                    {'label': "# Shapes Order", 'type': "number", 'default': 4, 'path': 'Session.Params.shapesOrder', 'description': "Number of shapes required to complete one order."},
                    {'label': "# Shapes Types", 'type': "number", 'default': 3, 'path': 'Session.Params.shapesTypes', 'description': "Number of distinct shape categories in the game."}
                ]
            }
        ],
        'interaction': {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': True,
                        'items': [0, 1, 2, 3, 4]
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' money, order progress).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Specialty Shape', 'path': 'Participant.specialty', 'control': 'shape', 'value': 'circle'},
                        {'label': 'Money', 'path': 'Participant.money', 'control': 'text'},
                        {'label': 'Production', 'path': 'Participant.production_number', 'control': 'text'},
                        {'label': 'Orders', 'path': 'Participant.order_progress', 'control': 'progress', 'value': 75}
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Action Structures": [
                {'label': "Negotiations", 'type': "boolean", 'default': "allow", 'options': ["Counter", "No Counter"], 'path': 'Session.Interaction.negotiations', 'description': "Counter: Participants can make counter offers. No Counter: Offers can only be accepted or rejected."},
                {'label': "Simultaneous Actions", 'type': "boolean", 'default': "allow", 'options': ["Allowed", "Not Allowed"], 'path': 'Session.Interaction.simultaneousActions', 'description': "Allow: Multiple offers can be made at once. Not Allow: Each offer must be resolved before a new one begins."},
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': False,
        },
        "interface": {
            "My Status": [
                {
                    "id": "my_status",
                    "label": "My Status",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "My Wealth",
                            "path": "Participant.wealth"
                        },
                        {
                            "label": "My Inventory",
                            "path": "Participant.inventory"
                        }
                    ]
                }
            ],
            "My Actions": [
                {
                    "id": "my_actions",
                    "label": "My Actions",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "My Specialty",
                            "path": "Participant.specialty",
                            "control": "shape"
                        },
                        {
                            "label": "Select a shape to produce",
                            "control": "shape_production",
                            "path": "Participant.shapes",
                            "options": "Participant.shapes"
                        },
                        {
                            "label": "In Production",
                            "path": "Participant.in_production"
                        }
                    ]
                }
            ],
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "",
                            "path": "Participant.tasks",
                            "control": "checkbox",
                            "on_check": "submit_shape"
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["trade", "messages"],
                    "trade_panel": {
                        "visible_if": "always",
                        "bindings": [
                            {
                                "label": "I want to {trade_action} one {shape_type} from/to {participant_name} at ${trade_price}",
                                "control": "trade_form",
                                "on_submit": "submit_trade",
                                "fields": {
                                    "trade_action": {
                                        "control": "segmented",
                                        "options": ["buy", "sell"],
                                        "default": "buy",
                                        "path": "Participant.trade_action"
                                    },
                                    "shape_type": {
                                        "control": "shape_production",
                                        "options": "Participant.shapes",
                                        "path": "Participant.trade_shape"
                                    },
                                    "participant_name": {
                                        "control": "text",
                                        "path": "Participant.selected_trade_participant",
                                        "readonly": True
                                    },
                                    "trade_price": {
                                        "control": "text",
                                        "path": "Participant.trade_price",
                                        "default": 20
                                    }
                                }
                            },
                            {
                                "label": "Pending Trade Offers",
                                "control": "trade_offers_list",
                                "path": "Session.pending_trade_offers"
                            },
                            {
                                "label": "Trade History",
                                "control": "trade_history_list",
                                "path": "Session.trade_history"
                            }
                        ]
                    }
                }
            ],
            "Info Dashboard": [
                {
                    "id": "info_dashboard",
                    "label": "Info Dashboard",
                    "visible_if": "Session.Interaction.awarenessDashboard.enabled",
                    "bindings": [
                        {
                            "label": "Name",
                            "path": "Participant.name",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.name')"
                        },
                        {
                            "label": "Specialty Shape",
                            "path": "Participant.specialty",
                            "control": "shape",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.specialty')"
                        },
                        {
                            "label": "Money",
                            "path": "Participant.money",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.money')"
                        },
                        {
                            "label": "Production",
                            "path": "Participant.production_number",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.production_number')"
                        },
                        {
                            "label": "Orders",
                            "path": "Participant.order_progress",
                            "control": "progress",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.order_progress')"
                        }
                    ]
                }
            ]
        },
        "annotation": {
            "enabled": False,
            "checkpoints": [20, 45, 70]
        }
    },
    {
        'id': 'daytrader',
        'name': 'DayTrader',
        'description': '**Setup:** Market-style investment game where participants can invest individually with safe returns or collectively with higher risk shared across the group.\n\n**Communication:** Occurs through assigned media channels.\n\n**Goal:** Optimize gains by balancing individual safety with group risk.',
        'tags': ['Social Dilemma', 'Trade'],
        'params': [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Money": [
                    {'label': "Participant Initial Money ($)", 'type': "number", 'default': 200, 'path': 'Session.Params.startingMoney'},
                    {'label': "Min. Trade Price ($)", 'type': "number", 'default': 15, 'path': 'Session.Params.minTradePrice'},
                    {'label': "Max. Trade Price ($)", 'type': "number", 'default': 100, 'path': 'Session.Params.maxTradePrice'},
                    {'label': "Order Incentive ($/trade fulfilled)", 'type': "number", 'default': 60, 'path': 'Session.Params.incentiveMoney'}
                ]
            }
        ],
        'interaction': {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': True,
                        'items': [0, 1]
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' money, order investment).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Money', 'path': 'Participant.money', 'control': 'text'},
                        {'label': 'Investment', 'path': 'Participant.investment_history', 'control': 'investment_history'}
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': False,
        },
        "interface": {
            "My Status": [
                {
                    "id": "my_status",
                    "label": "My Status",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "My Wealth",
                            "path": "Participant.wealth"
                        }
                    ]
                }
            ],
            "My Actions": [
                {
                    "id": "my_actions",
                    "label": "My Actions",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "I want to invest at ${investment_amount} as a {investment_type} decision.",
                            "control": "investment_form",
                            "on_submit": "submit_investment",
                            "fields": {
                                "investment_amount": {
                                    "control": "text",
                                    "type": "number",
                                    "min": 0,
                                    "default": 0,
                                    "placeholder": "Enter amount"
                                },
                                "investment_type": {
                                    "control": "segmented",
                                    "options": ["individual", "group"],
                                    "default": "individual"
                                }
                            }
                        }
                    ]
                }
            ],
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "Investment History",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Investment History",
                            "path": "Participant.investment_history"
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ],
            "Info Dashboard": [
                {
                    "id": "info_dashboard",
                    "label": "Info Dashboard",
                    "visible_if": "Session.Interaction.awarenessDashboard.enabled",
                    "bindings": [
                        {
                            "label": "Name",
                            "path": "Participant.name",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.name')"
                        },
                        {
                            "label": "Money",
                            "path": "Participant.money",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.money')"
                        },
                        {
                            "label": "Investment",
                            "path": "Participant.investment_history",
                            "control": "investment_history",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.investment_history')"
                        }
                    ]
                }
            ]
        },
        "annotation": {
            "enabled": False,
            "checkpoints": [20, 45, 70]
        }
    },
    {
        'id': 'essayranking',
        'name': 'Essay Ranking',
        'description': '**Setup:** Participants read and discuss essays, then vote to produce a collective ranking.\n\n**AI Integration:** In some settings, AI agents contribute votes or reasoning alongside humans.\n\n**Goal:** Reach consensus on rankings.',
        'tags': ['Collaborative Decision Making'],
        'params': [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Essay Parameters": [
                    {'label': "# Essays", 'type': "number", 'default': 5, 'path': 'Session.Params.essayNumber'},
                    {'label': "Upload Essays", 'type': "file", 'default': None, 'path': 'Session.Params.essays'},
                ]
            }
        ],
        'interaction': {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': True,
                        'items': [0, 1],
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' rankings).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Rankings', 'path': 'Participant.rankings', 'control': 'rankings'},
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': False,
        },
        "interface": {
            "My Status": [
                {
                    "id": "my_status",
                    "label": "My Status",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "My Inventory",
                            "path": "Participant.essays"
                        }
                    ]
                }
            ],
            "My Actions": [
                {
                    "id": "my_actions",
                    "label": "My Actions",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "I want to rank {essay_name} at {essay_rank}",
                            "on_submit": "submit_essay_rank",
                            "fields": {
                                "essay_name": {
                                    "control": "list",
                                    "options": "Participant.essays",
                                    "path": "Participant.selected_essay"
                                },
                                "essay_rank": {
                                    "control": "text",
                                    "control_type": "number",
                                    "min": 1,
                                    "max": len("Participant.essays"),
                                    "path": "Participant.selected_essay_rank"
                                }
                            }
                        }
                    ]
                }
            ],
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Please read and rank the essays. You may also send messages to discuss your thoughts with other participants",
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ],
            "Info Dashboard": [
                {
                    "id": "info_dashboard",
                    "label": "Info Dashboard",
                    "visible_if": "Session.Interaction.awarenessDashboard.enabled",
                    "bindings": [
                        {
                            "label": "Name",
                            "path": "Participant.name",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.name')"
                        },
                        {
                            "label": "Rankings",
                            "path": "Participant.rankings",
                            "control": "rankings",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.rankings')"
                        }
                    ]
                }
            ]
        },
        "annotation": {
            "enabled": False,
            "checkpoints": [20, 45, 70]
        }
    },
    {
        'id': 'wordguessing',
        'name': 'Word-Guessing Game',
        'description': '**Setup:** one participant tries to guess a word the other participant is thinking of, and the other participant only provides one word hint each round.\n\n**Goal:** investigate people\'s mental models of AI',
        'tags': ['Turn-Taking'],
        'params': [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Word Settings": [
                    {'label': "Word List", 'type': "input", 'default': "apple, banana, cherry, date, elderberry", 'path': 'Session.Params.wordList'}
                ]
            }
        ],
        'interaction': {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': False,
        },
        "interface": {
            "My Status": [
                {
                    "id": "my_status",
                    "label": "My Status",
                    "visible_if": "Participant.role == 'hinter'",
                    "bindings": [
                        {
                            "label": "My Words",
                            "path": "Participant.word_list",
                            "control": "list",
                            "options": "Participant.word_list"
                        }
                    ]
                }
            ],
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Please guess the word the other participant is thinking of. You may also send messages to discuss your thoughts with other participants",
                            "visible_if": "Participant.role == 'guesser'"
                        },
                        {
                            "label": "Please provide one-word hints to help the other participant guess your word. You may also send messages to discuss your thoughts with other participants",
                            "visible_if": "Participant.role == 'hinter'"
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ]
        },
        "annotation": {
            "enabled": False,
            "checkpoints": [20, 45, 70]
        }
    },
    {
        "id": "hiddenprofile",
        "name": "Hidden Profile",
        "description": "**Setup:** participants are given assymetric information about job candidates.\n\n**Goal:** vote on the best candidate through discussion",
        "tags": ["Collaborative Decision Making"],
        "params": [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Hidden Profile Settings": [
                    {'label': "Reading Time (minutes)", 'type': "number", 'default': 1, 'path': 'Session.Params.readingTime', 'description': "Time limit for reading the candidate document."},
                    {'label': "Candidate Names", 'type': "input_list", 'default': "", 'path': 'Session.Params.candidateNames', 'description': "Enter the names of the candidates and click 'Add' to add them to the list."},
                    {'label': "Participant Viewable Documents", 'type': "file", 'default': None, 'path': 'Session.Params.candidateDocuments', 'description': "Upload the documents that will be visible to the participants."},
                ]
            }
        ],
        "interaction": {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
            ],
            "Awareness Dashboard": [
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': True,
                        'items': [0, 1],
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' initial votes).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Initial Vote', 'path': 'Participant.initial_vote', 'control': 'text'},
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': True,
        },
        "interface": {
            "My Status": [
                {
                    "id": "my_status",
                    "label": "My Status",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "My Initial Vote",
                            "path": "Participant.initial_vote",
                            "control": "text",
                        }
                    ]
                }
            ],
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Review the public information and your assigned candidate document to make an informed decision. \n Use the discussion area to communicate with other participants.",
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ],
            "Reading Window": [
                {
                    "id": "reading_window",
                    "label": "Reading Window",
                    "visible_if": "on_enter",
                    "type": "popup",
                    "content": "Participant.candidate_document",
                    "bindings": [
                        {
                            "label": "Remaining Time",
                            "path": "Session.Params.readingTime",
                            "control": "timer"
                        }
                    ]
                }
            ],
            "Initial Vote": [
                {
                    "id": "initial_vote",
                    "label": "Vote for your preferred candidate",
                    "visible_if": "reading_window.on_end",
                    'type': 'popup',
                    "bindings": [
                        {
                            "label": "Please select your preferred candidate based on the material you have read",
                            "type": "list",
                            "options": "Session.Params.candidateNames",
                            "path": "Participant.selected_candidate",
                            "on_submit": "submit_initial_vote"
                        }
                    ]
                }
            ],
            "Final Vote": [
                {
                    "id": "final_vote",
                    "label": "Vote for your preferred candidate",
                    "visible_if": "on_end",
                    'type': 'popup',
                    "bindings": [
                        {
                            "label": "Please select your preferred candidate based on the material you have read",
                            "type": "list",
                            "options": "Session.Params.candidateNames",
                            "path": "Participant.selected_candidate",
                            "on_submit": "submit_final_vote"
                        }
                    ]
                }
            ]
        },
        "annotation": {
            "enabled": False,
            "checkpoints": [20, 45, 70]
        }
    },
    {
        "id": "maptask",
        "name": "The Map Task",
        "description": "**Setup: ** A guider is given a map including the landmarks and a route. A follower is gievn a map with landmarks only. **Communication: ** The two participants can send messages to each other. **Goal: ** The two participants need to collaborate to let the follower reproduce the route.",
        "tags": ["Turn-Taking"],
        "params": [
            {
                "General Settings": [
                    {'label': "Session Duration (min)", 'type': "number", 'default': 30, 'path': 'Session.Params.duration'}
                ],
                "Map Settings": [
                    {'label': "Maps", 'type': "file", 'default': None, 'path': 'Session.Params.maps', 'description': "Upload the maps that will be used in the session.", 'control': 'map_upload'},
                ]
            }
        ],
        "interaction": {
            "Information Flow": [
                {'label': "Communication Level", 'type': "list", 'default': "Private Messaging", 'options': [{"Private Messaging": "Participants can send private one-to-one messages"}, {"Group Chat": "All participants can see and send messages in a group"}, {"No Chat": "Messaging disabled; no communication possible."}], 'path': 'Session.Interaction.communicationLevel', 'description': "Private Messaging: Direct messaging between participants. Group Chat: Public messages visible to all. No Chat: No communication allowed."},
                {'label': "Communication Media", 'type': "multi_checkbox", 'default': ["text"], 'options': [{"label": "Text Message", "value": "text", "description": "Participants type messages"}, {"label": "Audio", "value": "audio", "description": "Voice input with Whisper transcription"}, {"label": "Meeting Room", "value": "meeting_room", "description": "Real-time video/audio like Zoom"}], 'path': 'Session.Interaction.communicationMedia', 'description': "Select which communication media to enable. Text: type messages. Audio: voice input with transcription. Meeting Room: real-time video/audio."},
                {'label': "Type Indicator", 'type': "boolean", 'default': "not_enabled", 'options': ["Enabled", "Not Enabled"], 'path': 'Session.Interaction.typeIndicator', 'description': "When enabled, others see who is currently typing in the text chat (private threads or group chat)."},
                {
                    'label': "Awareness Dashboard",
                    'type': "tiered_checkbox",
                    'default': {
                        'enabled': False,
                        'items': [0, 1],
                    },
                    'description': "Enable the Awareness Dashboard for participants. When enabled, select the information items to display to participants (e.g., others' map progress).",
                    'options': [
                        {'label': 'Name', 'path': 'Participant.name', 'control': 'text'},
                        {'label': 'Map Progress', 'path': 'Participant.map_progress', 'control': 'map_progress'},
                    ],
                    'path': 'Session.Interaction.awarenessDashboard',
                }
            ],
            "Action Structures": [
                {'label': 'message_length', 'type': 'boolean_number', 'default': False, 'path': 'Session.Interaction.messageLength', 'description': 'Maximum length of the message sent by participants.'},
            ],
            "Agent Behaviors": [
                {'label': "Agent Perception Time Window (sec)", 'type': "number", 'default': 15, 'path': 'Session.Interaction.agentPerceptionTimeWindow', 'description': "Frequency (in seconds) at which agents update their view of the game state."},
                {'label': "Rationales", 'type': "boolean", 'default': "step_wise", 'options': ["Step-wise", "None"], 'path': 'Session.Interaction.rationales', 'description': "Step-wise: Agents explain each decision with reasoning. None: Agents act without providing reasoning."},
            ]
        },
        "participant_settings": {
            'auto_start': False,
        },
        "interface": {
            "My Tasks": [
                {
                    "id": "my_tasks",
                    "label": "My Tasks",
                    "visible_if": "true",
                    "bindings": [
                        {
                            "label": "Your Map",
                            "path": "Participant.map",
                            "control": "map",
                            "default": None
                        },
                        {
                            "label": "Your toolbox",
                            "visible_if": "Participant.role == 'follower'",
                            "default": None,
                            "control": "map_toolbox"
                        }
                    ]
                }
            ],
            "Social Panel": [
                {
                    "id": "social_panel",
                    "label": "Social Panel",
                    "visible_if": "true",
                    "bindings": [],
                    "tabs": ["messages"],
                }
            ],
            "Info Dashboard": [
                {
                    "id": "info_dashboard",
                    "label": "Info Dashboard",
                    "visible_if": "Session.Interaction.awarenessDashboard.enabled && Participant.role == 'guider'",
                    "bindings": [
                        {
                            "label": "Name",
                            "path": "Participant.name",
                            "control": "text",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.name')"
                        },
                        {
                            "label": "Map Progress",
                            "path": "Participant.map_progress",
                            "control": "map_progress",
                            "visible_if": "Session.Interaction.awarenessDashboard.items.contains('Participant.map_progress')"
                        }
                    ]
                }
            ]
        },
        "annotation": {
            "enabled": True,
            "checkpoints": [20, 45, 70]
        }
    }
]

PARTICIPANTS = [
    {
        "shapefactory": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "specialty": {
                        "type": "string",
                        # Expanded default shape pool (will still be limited by Session.Params.shapesTypes where applicable)
                        "options": ["circle", "square", "triangle", "rectangle", "diamond", "pentagon", "hexagon", "star"],
                        "control": "shape",
                        "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "money": {
                        "type": "number",
                        "default": 0,
                        "init_path": "Session.Params.startingMoney"
                    },
                    "production_number": {
                        "type": "number",
                        "default": 0,
                        "init_path": None
                    },
                    "order_progress": {
                        "type": "number",
                        "default": 0,
                        "init_path": None
                    },
                    "inventory": {
                        "type": "list",
                        "options": ["circle", "square", "triangle", "rectangle", "diamond", "pentagon", "hexagon", "star"],
                        "default": [],
                        "init_path": None
                    },
                    "shapes": {
                        "type": "list",
                        "options": ["circle", "square", "triangle", "rectangle", "diamond", "pentagon", "hexagon", "star"],
                        "options_limit_path": "Session.Params.shapesTypes",
                        "init_path": None
                    },
                    "in_production": {
                        "type": "list",
                        "options": ["circle", "square", "triangle", "rectangle", "diamond", "pentagon", "hexagon", "star"],
                        "options_limit_path": "Session.Params.shapesTypes",
                        "default": [],
                        "init_path": None
                    },
                    "tasks": {
                        "type": "list",
                        "options": ["circle", "square", "triangle", "rectangle", "diamond", "pentagon", "hexagon", "star"],
                        "options_limit_path": "Session.Params.shapesTypes",
                        "default": [],
                        "init_path": "Functions.assign_tasks"
                    }
                }
            }
        ],
        "daytrader": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "money": {
                        "type": "number",
                        "default": 0,
                        "init_path": "Session.Params.startingMoney"
                    },
                    "investment_history": {
                        "type": "list",
                        "default": [],
                        "init_path": None
                    }
                }
            }
        ],
        "essayranking": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "essays": {
                        "type": "list",
                        "default": [],
                        "init_path": "Session.essays"
                    },
                    "rankings": {
                        "type": "list",
                        "default": [],
                        "init_path": None
                    }
                }
            }
        ],
        "wordguessing": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "role": {
                    "type": "string",
                    "options": ["guesser", "hinter"],
                    "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "word_list": {
                        "type": "list",
                        "default": [],
                        "init_path": "Session.Params.wordList"
                    }
                }
            }
        ],
        "hiddenprofile": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "initial_vote": {
                        "type": "string",
                        "default": "none",
                        "init_path": None
                    },
                    "final_vote": {
                        "type": "string",
                        "default": "none",
                        "init_path": None
                    },
                    "candidate_document": {
                        "type": "file",
                        "default": None,
                        "init_path": None
                    }
                }
            }
        ],
        "maptask": [
            {
                "id": {
                    "type": "uuid",
                    "default": ""
                },
                "name": {
                    "type": "string",
                    "default": ""
                },
                "type": {
                    "type": "string",
                    "options": ["human", "ai"],
                    "default": ""
                },
                "role": {
                    "type": "string",
                    "options": ["guider", "follower"],
                    "default": ""
                },
                "mbti": {
                    "type": "string",
                    "options": ["INTJ", "ENTJ", "INFJ", "ENFJ", "INFP", "ENFP", "INTP", "ENTP", "ISTP", "ESTP", "ISFP", "ESFP", "ISTJ", "ESTJ", "ISFJ", "ESFJ", "unknown"],
                    "default": ""
                },
                "experiment_params": {
                    "map": {
                        "type": "file",
                        "default": None,
                        "init_path": "Functions.assign_map_for_maptask"
                    },
                    "map_progress": {
                        "type": "object",
                        "default": None,
                        "init_path": None
                    }
                }
            }
        ]
    }
]

def get_experiment_by_id(experiment_id):
    """Get experiment config by ID"""
    for exp in EXPERIMENTS:
        if exp['id'] == experiment_id:
            return exp
    return None

def get_participant_by_id(participant_id):
    """Get participant config by ID"""
    for participant in PARTICIPANTS:
        if participant['id'] == participant_id:
            return participant
    return None
