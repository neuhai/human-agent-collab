--
-- PostgreSQL database dump
--

\restrict FbfWS1zFxrQIIPXIuD5aa2luRUo9S0K2ifpzhLL4JugQ54rmHmU8ERrvnGXMfd8

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: cleanup_old_notifications(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.cleanup_old_notifications() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM dashboard_notifications 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '24 hours'
    AND delivered_to_dashboard = TRUE;
    
    DELETE FROM participant_status_log 
    WHERE status_change_timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days';
END;
$$;


ALTER FUNCTION public.cleanup_old_notifications() OWNER TO postgres;

--
-- Name: complete_production_items(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.complete_production_items() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Update production status to completed for items past their completion time
    UPDATE production_queue 
    SET production_status = 'completed',
        actual_completion_time = CURRENT_TIMESTAMP
    WHERE production_status = 'in_progress' 
    AND expected_completion_time <= CURRENT_TIMESTAMP;
    
    -- Add completed shapes to inventory
    INSERT INTO shape_inventory (round_id, participant_id, shape_name, quantity, source_type, source_details)
    SELECT 
        pq.round_id,
        pq.participant_id,
        pq.shape_name,
        pq.quantity,
        'production'::text,
        jsonb_build_object('production_id', pq.production_id, 'cost', pq.total_cost)
    FROM production_queue pq
    WHERE pq.production_status = 'completed'
    AND pq.actual_completion_time = (
        SELECT MAX(actual_completion_time) 
        FROM production_queue 
        WHERE production_id = pq.production_id
    );
END;
$$;


ALTER FUNCTION public.complete_production_items() OWNER TO postgres;

--
-- Name: complete_transaction(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.complete_transaction() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
IF NEW.transaction_status = 'completed' AND OLD.transaction_status != 'completed' THEN
UPDATE shape_inventory
SET shapes_in_inventory = shapes_in_inventory - NEW.quantity,
last_updated = CURRENT_TIMESTAMP
WHERE session_id = NEW.session_id
AND participant_id = NEW.seller_id
AND shapes_in_inventory @> jsonb_build_array(NEW.shape_type);
UPDATE shape_inventory
SET shapes_in_inventory = shapes_in_inventory || jsonb_build_array(NEW.shape_type),
last_updated = CURRENT_TIMESTAMP
WHERE session_id = NEW.session_id
AND participant_id = NEW.buyer_id;
UPDATE participants
SET money = money + (NEW.agreed_price * NEW.quantity)
WHERE participant_id = NEW.seller_id;
UPDATE participants
SET money = money - (NEW.agreed_price * NEW.quantity)
WHERE participant_id = NEW.buyer_id;
END IF;
RETURN NEW;
END;
$$;


ALTER FUNCTION public.complete_transaction() OWNER TO postgres;

--
-- Name: FUNCTION complete_transaction(); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.complete_transaction() IS 'DISABLED: This function was causing duplicate inventory updates. Inventory updates are now handled directly in game_engine.py';


--
-- Name: create_dashboard_notification(uuid, character varying, jsonb); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.create_dashboard_notification(session_uuid uuid, notif_type character varying, notif_data jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO dashboard_notifications (session_id, notification_type, notification_data)
    VALUES (session_uuid, notif_type, notif_data);
END;
$$;


ALTER FUNCTION public.create_dashboard_notification(session_uuid uuid, notif_type character varying, notif_data jsonb) OWNER TO postgres;

--
-- Name: generate_short_session_id(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.generate_short_session_id() RETURNS character varying
    LANGUAGE plpgsql
    AS $_$
DECLARE
    next_id INTEGER;
BEGIN
    -- Get the next sequence number for sessions
    SELECT COALESCE(MAX(CAST(SUBSTRING(short_id FROM 2) AS INTEGER)), 0) + 1 
    INTO next_id 
    FROM sessions 
    WHERE short_id IS NOT NULL AND short_id ~ '^S[0-9]+$';
    
    RETURN 'S' || next_id::TEXT;
END;
$_$;


ALTER FUNCTION public.generate_short_session_id() OWNER TO postgres;

--
-- Name: generate_short_transaction_id(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.generate_short_transaction_id(session_short_id character varying) RETURNS character varying
    LANGUAGE plpgsql
    AS $_$
DECLARE
    next_seq INTEGER;
BEGIN
    -- Get the next sequence number for transactions in this session
    SELECT COALESCE(MAX(CAST(SUBSTRING(short_id FROM LENGTH(session_short_id) + 2) AS INTEGER)), 0) + 1 
    INTO next_seq 
    FROM transactions 
    WHERE short_id IS NOT NULL 
    AND short_id LIKE session_short_id || '-%'
    AND short_id ~ '^S[0-9]+-[0-9]+$';
    
    RETURN session_short_id || '-' || LPAD(next_seq::TEXT, 3, '0');
END;
$_$;


ALTER FUNCTION public.generate_short_transaction_id(session_short_id character varying) OWNER TO postgres;

--
-- Name: get_most_active_participant(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_most_active_participant(p_code character varying) RETURNS TABLE(participant_id uuid, session_id uuid, session_code character varying, participant_code character varying, last_activity_timestamp timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.participant_id,
        p.session_id,
        p.session_code,
        p.participant_code,
        p.last_activity_timestamp
    FROM participants p
    WHERE p.participant_code = p_code
    ORDER BY p.last_activity_timestamp DESC NULLS LAST, p.created_at DESC
    LIMIT 1;
END;
$$;


ALTER FUNCTION public.get_most_active_participant(p_code character varying) OWNER TO postgres;

--
-- Name: FUNCTION get_most_active_participant(p_code character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_most_active_participant(p_code character varying) IS 'Get the most active participant for a given participant_code across all sessions';


--
-- Name: get_session_agents(character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_session_agents(session_code_param character varying) RETURNS TABLE(participant_code character varying, agent_type character varying, specialty_shape character varying, agent_status character varying, money integer)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.participant_code,
        p.agent_type,
        p.specialty_shape,
        p.agent_status,
        p.money
    FROM participants p
    WHERE p.session_code = session_code_param 
    AND p.is_agent = true;
END;
$$;


ALTER FUNCTION public.get_session_agents(session_code_param character varying) OWNER TO postgres;

--
-- Name: get_session_participant(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_session_participant(p_code character varying, s_code character varying) RETURNS TABLE(participant_id uuid, session_id uuid, session_code character varying, participant_code character varying, last_activity_timestamp timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.participant_id,
        p.session_id,
        p.session_code,
        p.participant_code,
        p.last_activity_timestamp
    FROM participants p
    WHERE p.participant_code = p_code AND p.session_code = s_code
    LIMIT 1;
END;
$$;


ALTER FUNCTION public.get_session_participant(p_code character varying, s_code character varying) OWNER TO postgres;

--
-- Name: FUNCTION get_session_participant(p_code character varying, s_code character varying); Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON FUNCTION public.get_session_participant(p_code character varying, s_code character varying) IS 'Get a specific participant by participant_code and session_code';


--
-- Name: notify_new_message(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.notify_new_message() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Create dashboard notification
    PERFORM create_dashboard_notification(
        NEW.session_id,
        'new_message',
        jsonb_build_object(
            'message_id', NEW.message_id,
            'sender_id', NEW.sender_id,
            'recipient_id', NEW.recipient_id,
            'message_type', NEW.message_type,
            'content_preview', LEFT(NEW.message_content, 100),
            'timestamp', NEW.message_timestamp
        )
    );
    
    -- Update real-time metrics
    PERFORM update_session_metrics(NEW.session_id);
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.notify_new_message() OWNER TO postgres;

--
-- Name: notify_new_transaction(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.notify_new_transaction() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    session_uuid UUID;
BEGIN
    -- Get session_id directly from transaction
    session_uuid := NEW.session_id;
    
    -- Create dashboard notification
    PERFORM create_dashboard_notification(
        session_uuid,
        'new_transaction',
        jsonb_build_object(
            'transaction_id', NEW.transaction_id,
            'seller_id', NEW.seller_id,
            'buyer_id', NEW.buyer_id,
            'shape_type', NEW.shape_type,
            'quantity', NEW.quantity,
            'agreed_price', NEW.agreed_price,
            'status', NEW.transaction_status,
            'timestamp', NEW.proposed_timestamp
        )
    );
    
    -- Update real-time metrics
    PERFORM update_session_metrics(session_uuid);
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.notify_new_transaction() OWNER TO postgres;

--
-- Name: notify_participant_status_change(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.notify_participant_status_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Log the status change
    INSERT INTO participant_status_log (participant_id, session_id, previous_status, new_status, change_reason)
    VALUES (NEW.participant_id, NEW.session_id, OLD.login_status, NEW.login_status, 'status_update');
    
    -- Create dashboard notification
    PERFORM create_dashboard_notification(
        NEW.session_id,
        'participant_status_change',
        jsonb_build_object(
            'participant_id', NEW.participant_id,
            'participant_code', NEW.participant_code,
            'participant_type', NEW.participant_type,
            'old_status', OLD.login_status,
            'new_status', NEW.login_status,
            'timestamp', CURRENT_TIMESTAMP
        )
    );
    
    -- Update real-time metrics
    PERFORM update_session_metrics(NEW.session_id);
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.notify_participant_status_change() OWNER TO postgres;

--
-- Name: set_session_short_id(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_session_short_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.short_id IS NULL THEN
        NEW.short_id := generate_short_session_id();
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_session_short_id() OWNER TO postgres;

--
-- Name: set_transaction_short_id(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_transaction_short_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.short_id IS NULL THEN
        NEW.short_id := generate_short_transaction_id(
            (SELECT short_id FROM sessions WHERE session_id = NEW.session_id)
        );
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_transaction_short_id() OWNER TO postgres;

--
-- Name: update_agent_status(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_agent_status(participant_code_param character varying, new_status character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE participants 
    SET agent_status = new_status,
        last_activity = CURRENT_TIMESTAMP
    WHERE participant_code = participant_code_param 
    AND is_agent = true;
    
    RETURN FOUND;
END;
$$;


ALTER FUNCTION public.update_agent_status(participant_code_param character varying, new_status character varying) OWNER TO postgres;

--
-- Name: update_participant_activity(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_participant_activity() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE participants 
    SET last_activity_timestamp = CURRENT_TIMESTAMP 
    WHERE participant_id = NEW.sender_id;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_participant_activity() OWNER TO postgres;

--
-- Name: update_production_queue_timestamp(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_production_queue_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_production_queue_timestamp() OWNER TO postgres;

--
-- Name: update_session_metrics(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_session_metrics(session_uuid uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO session_metrics_realtime (session_id, total_participants, online_participants,
                                        human_participants_online, ai_participants_online,
                                        active_transactions, completed_transactions, total_messages)
    SELECT 
        s.session_id,
        COUNT(p.participant_id) as total_participants,
        COUNT(CASE WHEN p.login_status = 'active' THEN 1 END) as online_participants,
        COUNT(CASE WHEN p.login_status = 'active' AND p.participant_type = 'human' THEN 1 END) as human_participants_online,
        COUNT(CASE WHEN p.login_status = 'active' AND p.participant_type = 'ai_agent' THEN 1 END) as ai_participants_online,
        COALESCE(t.active_transactions, 0) as active_transactions,
        COALESCE(t.completed_transactions, 0) as completed_transactions,
        COALESCE(m.total_messages, 0) as total_messages
    FROM sessions s
    LEFT JOIN participants p ON s.session_id = p.session_id
    LEFT JOIN (
        SELECT session_id, 
               COUNT(CASE WHEN transaction_status IN ('proposed', 'negotiating', 'agreed') THEN 1 END) as active_transactions,
               COUNT(CASE WHEN transaction_status = 'completed' THEN 1 END) as completed_transactions
        FROM transactions t
        WHERE t.session_id = session_uuid
        GROUP BY session_id
    ) t ON s.session_id = t.session_id
    LEFT JOIN (
        SELECT session_id, COUNT(*) as total_messages
        FROM messages
        WHERE session_id = session_uuid
        GROUP BY session_id
    ) m ON s.session_id = m.session_id
    WHERE s.session_id = session_uuid
    GROUP BY s.session_id, t.active_transactions, t.completed_transactions, m.total_messages
    ON CONFLICT (session_id) DO UPDATE SET
        total_participants = EXCLUDED.total_participants,
        online_participants = EXCLUDED.online_participants,
        human_participants_online = EXCLUDED.human_participants_online,
        ai_participants_online = EXCLUDED.ai_participants_online,
        active_transactions = EXCLUDED.active_transactions,
        completed_transactions = EXCLUDED.completed_transactions,
        total_messages = EXCLUDED.total_messages,
        last_updated = CURRENT_TIMESTAMP;
END;
$$;


ALTER FUNCTION public.update_session_metrics(session_uuid uuid) OWNER TO postgres;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_agent_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ai_agent_logs (
    log_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    log_type character varying(30) NOT NULL,
    log_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    reasoning_data jsonb NOT NULL,
    game_state_snapshot jsonb,
    triggered_by_event character varying(100),
    CONSTRAINT ai_agent_logs_log_type_check CHECK (((log_type)::text = ANY (ARRAY[('decision_making'::character varying)::text, ('strategy_update'::character varying)::text, ('perception'::character varying)::text, ('memory_update'::character varying)::text, ('action_execution'::character varying)::text])))
);


ALTER TABLE public.ai_agent_logs OWNER TO postgres;

--
-- Name: dashboard_notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dashboard_notifications (
    notification_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    notification_type character varying(30) NOT NULL,
    notification_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    delivered_to_dashboard boolean DEFAULT false,
    delivered_at timestamp with time zone,
    CONSTRAINT dashboard_notifications_notification_type_check CHECK (((notification_type)::text = ANY (ARRAY[('participant_status_change'::character varying)::text, ('new_transaction'::character varying)::text, ('new_message'::character varying)::text, ('round_status_change'::character varying)::text, ('system_alert'::character varying)::text])))
);


ALTER TABLE public.dashboard_notifications OWNER TO postgres;

--
-- Name: essay_assignments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.essay_assignments (
    assignment_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    essay_id character varying(50) NOT NULL,
    essay_title text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    essay_content text,
    essay_filename character varying(255),
    essay_metadata jsonb
);


ALTER TABLE public.essay_assignments OWNER TO postgres;

--
-- Name: TABLE essay_assignments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.essay_assignments IS 'Simplified essay assignments for essayranking experiments - only essay_id and title needed';


--
-- Name: COLUMN essay_assignments.essay_content; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.essay_assignments.essay_content IS 'Extracted text content from PDF essays';


--
-- Name: COLUMN essay_assignments.essay_filename; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.essay_assignments.essay_filename IS 'Original filename of the uploaded PDF';


--
-- Name: COLUMN essay_assignments.essay_metadata; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.essay_assignments.essay_metadata IS 'Additional metadata about the essay (word count, reading time, etc.)';


--
-- Name: investments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.investments (
    invest_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    invest_price numeric(10,2) NOT NULL,
    invest_decision_type character varying(20) NOT NULL,
    invest_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    invest_data jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT investments_invest_decision_type_check CHECK (((invest_decision_type)::text = ANY (ARRAY[('individual'::character varying)::text, ('group'::character varying)::text])))
);


ALTER TABLE public.investments OWNER TO postgres;

--
-- Name: TABLE investments; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.investments IS 'Investment records for DayTrader experiments';


--
-- Name: COLUMN investments.invest_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.investments.invest_price IS 'Price at which the investment was made';


--
-- Name: COLUMN investments.invest_decision_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.investments.invest_decision_type IS 'Whether decision was made individually or as part of a group';


--
-- Name: COLUMN investments.invest_data; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.investments.invest_data IS 'Additional investment metadata in JSON format';


--
-- Name: participants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.participants (
    participant_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    participant_code character varying(50) NOT NULL,
    participant_type character varying(10) NOT NULL,
    color_shape_combination character varying(50) NOT NULL,
    specialty_shape character varying(20) NOT NULL,
    login_status character varying(20) DEFAULT 'not_logged_in'::character varying NOT NULL,
    login_timestamp timestamp with time zone,
    last_activity_timestamp timestamp with time zone,
    total_score integer DEFAULT 0,
    shapes_bought integer DEFAULT 0,
    shapes_sold integer DEFAULT 0,
    orders_completed integer DEFAULT 0,
    session_code character varying(50) NOT NULL,
    is_agent boolean DEFAULT false,
    agent_type character varying(50),
    agent_status character varying(20) DEFAULT 'inactive'::character varying,
    money integer DEFAULT 300,
    last_activity timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    tag character varying(50),
    orders jsonb DEFAULT '[]'::jsonb,
    specialty_production_used integer DEFAULT 0,
    mbti_type character varying(4),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    mturk_worker_id character varying(255),
    mturk_assignment_id character varying(255),
    mturk_hit_id character varying(255),
    prolific_pid character varying(255),
    prolific_study_id character varying(255),
    prolific_session_id character varying(255),
    is_preview boolean DEFAULT false,
    current_rankings jsonb DEFAULT '[]'::jsonb,
    submitted_rankings_count integer DEFAULT 0,
    role character varying(20) DEFAULT NULL::character varying,
    current_round integer DEFAULT 1,
    score integer DEFAULT 0,
    assigned_words jsonb DEFAULT '[]'::jsonb,
    CONSTRAINT check_agent_fields CHECK (((is_agent = false) OR ((is_agent = true) AND (agent_type IS NOT NULL)))),
    CONSTRAINT participants_login_status_check CHECK (((login_status)::text = ANY (ARRAY[('not_logged_in'::character varying)::text, ('logged_in'::character varying)::text, ('active'::character varying)::text, ('disconnected'::character varying)::text]))),
    CONSTRAINT participants_participant_type_check CHECK (((participant_type)::text = ANY (ARRAY[('human'::character varying)::text, ('ai_agent'::character varying)::text]))),
    CONSTRAINT participants_role_check CHECK (((role IS NULL) OR ((role)::text = ANY (ARRAY[('guesser'::character varying)::text, ('hinter'::character varying)::text]))))
);


ALTER TABLE public.participants OWNER TO postgres;

--
-- Name: COLUMN participants.last_activity_timestamp; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.last_activity_timestamp IS 'Timestamp of last activity for ordering in session-aware queries';


--
-- Name: COLUMN participants.session_code; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.session_code IS 'Human-readable session identifier for easier querying and session separation';


--
-- Name: COLUMN participants.is_agent; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.is_agent IS 'Whether this participant is an AI agent';


--
-- Name: COLUMN participants.agent_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.agent_type IS 'Type of AI agent (now always basic_agent)';


--
-- Name: COLUMN participants.agent_status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.agent_status IS 'Current status of AI agent (inactive, active, created)';


--
-- Name: COLUMN participants.money; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.money IS 'Current money balance for the participant';


--
-- Name: COLUMN participants.last_activity; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.last_activity IS 'Timestamp of last activity';


--
-- Name: COLUMN participants.tag; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.tag IS 'Optional tag for grouping participants (e.g., "Group A", "Test Agents")';


--
-- Name: COLUMN participants.orders; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.orders IS 'Static orders assigned to participant during registration (JSON array of shape names)';


--
-- Name: COLUMN participants.current_rankings; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.current_rankings IS 'Current essay rankings for essayranking experiment (JSON array)';


--
-- Name: COLUMN participants.submitted_rankings_count; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.submitted_rankings_count IS 'Number of ranking submissions completed';


--
-- Name: COLUMN participants.role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.role IS 'Role in wordguessing experiment: guesser or hinter';


--
-- Name: COLUMN participants.current_round; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.current_round IS 'Current round number in wordguessing experiment';


--
-- Name: COLUMN participants.score; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.score IS 'Current score in wordguessing experiment';


--
-- Name: COLUMN participants.assigned_words; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.participants.assigned_words IS 'Words assigned to hinter participant (JSON array)';


--
-- Name: mcp_agents; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.mcp_agents AS
 SELECT participant_id,
    participant_code,
    session_code,
    specialty_shape,
    money,
    agent_type,
    agent_status,
    last_activity,
    login_status,
    total_score,
    shapes_bought,
    shapes_sold,
    orders_completed
   FROM public.participants
  WHERE (is_agent = true);


ALTER VIEW public.mcp_agents OWNER TO postgres;

--
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    message_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    recipient_id uuid,
    message_type character varying(20) DEFAULT 'chat'::character varying NOT NULL,
    message_content text NOT NULL,
    message_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    message_data jsonb,
    delivered_status character varying(20) DEFAULT 'sent'::character varying NOT NULL,
    CONSTRAINT messages_delivered_status_check CHECK (((delivered_status)::text = ANY (ARRAY[('sent'::character varying)::text, ('delivered'::character varying)::text, ('read'::character varying)::text, ('failed'::character varying)::text]))),
    CONSTRAINT messages_message_type_check CHECK (((message_type)::text = ANY (ARRAY[('chat'::character varying)::text, ('transaction_request'::character varying)::text, ('transaction_response'::character varying)::text, ('system_notification'::character varying)::text])))
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- Name: mturk_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mturk_tasks (
    id integer NOT NULL,
    hit_id character varying(255) NOT NULL,
    session_id uuid,
    environment character varying(20) NOT NULL,
    status character varying(50) DEFAULT 'ASSOCIATED'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.mturk_tasks OWNER TO postgres;

--
-- Name: mturk_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mturk_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mturk_tasks_id_seq OWNER TO postgres;

--
-- Name: mturk_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mturk_tasks_id_seq OWNED BY public.mturk_tasks.id;


--
-- Name: participant_orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.participant_orders (
    order_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    participant_id uuid NOT NULL,
    required_shapes jsonb NOT NULL,
    order_completion_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    shapes_acquired jsonb DEFAULT '[]'::jsonb,
    completion_timestamp timestamp with time zone,
    order_score integer DEFAULT 0,
    session_id uuid NOT NULL,
    CONSTRAINT participant_orders_order_completion_status_check CHECK (((order_completion_status)::text = ANY (ARRAY[('pending'::character varying)::text, ('in_progress'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text])))
);


ALTER TABLE public.participant_orders OWNER TO postgres;

--
-- Name: participant_status_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.participant_status_log (
    status_log_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    participant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    previous_status character varying(20),
    new_status character varying(20) NOT NULL,
    status_change_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    change_reason character varying(50),
    ip_address inet,
    user_agent text
);


ALTER TABLE public.participant_status_log OWNER TO postgres;

--
-- Name: production_queue; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.production_queue (
    queue_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    participant_id uuid,
    shape_type character varying(20) NOT NULL,
    quantity integer DEFAULT 1 NOT NULL,
    estimated_completion_time timestamp with time zone NOT NULL,
    status character varying(20) DEFAULT 'in_progress'::character varying NOT NULL,
    queue_position integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.production_queue OWNER TO postgres;

--
-- Name: ranking_submissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ranking_submissions (
    submission_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    essay_rankings jsonb NOT NULL,
    submission_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    submission_metadata jsonb
);


ALTER TABLE public.ranking_submissions OWNER TO postgres;

--
-- Name: TABLE ranking_submissions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.ranking_submissions IS 'Participant ranking submissions - allows multiple submissions and adjustments';


--
-- Name: research_observations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.research_observations (
    observation_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    researcher_id character varying(100) NOT NULL,
    observation_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    observation_type character varying(30) NOT NULL,
    observation_content text NOT NULL,
    related_participant_id uuid,
    observation_data jsonb,
    CONSTRAINT research_observations_observation_type_check CHECK (((observation_type)::text = ANY (ARRAY[('behavioral_note'::character varying)::text, ('technical_issue'::character varying)::text, ('protocol_deviation'::character varying)::text, ('interesting_pattern'::character varying)::text])))
);


ALTER TABLE public.research_observations OWNER TO postgres;

--
-- Name: schema_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.schema_version (
    version character varying(10) NOT NULL,
    applied_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    description text
);


ALTER TABLE public.schema_version OWNER TO postgres;

--
-- Name: session_analytics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_analytics (
    analytics_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    total_transactions integer DEFAULT 0,
    human_to_human_transactions integer DEFAULT 0,
    human_to_ai_transactions integer DEFAULT 0,
    ai_to_human_transactions integer DEFAULT 0,
    ai_to_ai_transactions integer DEFAULT 0,
    average_human_score numeric(10,2),
    average_ai_score numeric(10,2),
    completion_rate numeric(5,2),
    in_group_bias_score numeric(5,3),
    communication_frequency jsonb,
    computed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.session_analytics OWNER TO postgres;

--
-- Name: session_metrics_realtime; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_metrics_realtime (
    session_id uuid NOT NULL,
    total_participants integer DEFAULT 0,
    online_participants integer DEFAULT 0,
    human_participants_online integer DEFAULT 0,
    ai_participants_online integer DEFAULT 0,
    current_round integer DEFAULT 0,
    active_transactions integer DEFAULT 0,
    completed_transactions integer DEFAULT 0,
    total_messages integer DEFAULT 0,
    average_response_time_ms integer DEFAULT 0,
    system_load_percentage numeric(5,2) DEFAULT 0,
    last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.session_metrics_realtime OWNER TO postgres;

--
-- Name: session_templates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_templates (
    template_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id character varying(20) NOT NULL,
    researcher_id character varying(100) NOT NULL,
    template_config jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_default boolean DEFAULT false
);


ALTER TABLE public.session_templates OWNER TO postgres;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sessions (
    session_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_code character varying(20) NOT NULL,
    experiment_type character varying(20),
    session_status character varying(20) DEFAULT 'idle'::character varying NOT NULL,
    researcher_id character varying(100) NOT NULL,
    total_rounds integer DEFAULT 5 NOT NULL,
    round_duration_minutes integer DEFAULT 15 NOT NULL,
    first_round_duration_minutes integer DEFAULT 20 NOT NULL,
    max_participants integer DEFAULT 10 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    setup_started_at timestamp with time zone,
    session_started_at timestamp with time zone,
    session_completed_at timestamp with time zone,
    experiment_config jsonb,
    short_id character varying(20),
    CONSTRAINT sessions_experiment_type_check CHECK ((((experiment_type)::text = ANY (ARRAY[('shapefactory'::character varying)::text, ('daytrader'::character varying)::text, ('essayranking'::character varying)::text, ('wordguessing'::character varying)::text, ('ecl_custom'::character varying)::text, ('hiddenprofiles'::character varying)::text])) OR ((experiment_type)::text ~~ 'custom_%'::text) OR (experiment_type IS NULL))),
    CONSTRAINT sessions_session_status_check CHECK (((session_status)::text = ANY (ARRAY[('idle'::character varying)::text, ('setup_complete'::character varying)::text, ('session_active'::character varying)::text, ('session_paused'::character varying)::text, ('session_completed'::character varying)::text]))),
    CONSTRAINT valid_session_timing CHECK ((((setup_started_at IS NULL) OR (setup_started_at >= created_at)) AND ((session_started_at IS NULL) OR (session_started_at >= setup_started_at)) AND ((session_completed_at IS NULL) OR (session_completed_at >= session_started_at))))
);


ALTER TABLE public.sessions OWNER TO postgres;

--
-- Name: COLUMN sessions.experiment_type; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.sessions.experiment_type IS 'Experiment type (shapefactory, daytrader, essayranking, wordguessing, hiddenprofiles, or custom_*). Can be NULL initially and set later when researcher selects experiment.';


--
-- Name: CONSTRAINT sessions_experiment_type_check ON sessions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON CONSTRAINT sessions_experiment_type_check ON public.sessions IS 'Allows valid experiment types: shapefactory, daytrader, essayranking, wordguessing, ecl_custom, hiddenprofiles, or custom_* (can also be NULL)';


--
-- Name: shape_inventory; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.shape_inventory (
    inventory_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    participant_id uuid NOT NULL,
    specialty_shapes_available integer DEFAULT 6 NOT NULL,
    specialty_shapes_sold integer DEFAULT 0 NOT NULL,
    shapes_in_inventory jsonb DEFAULT '[]'::jsonb,
    last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    session_id uuid NOT NULL
);


ALTER TABLE public.shape_inventory OWNER TO postgres;

--
-- Name: transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transactions (
    transaction_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    seller_id uuid NOT NULL,
    buyer_id uuid NOT NULL,
    shape_type character varying(20) NOT NULL,
    shape_color character varying(20),
    quantity integer DEFAULT 1 NOT NULL,
    agreed_price numeric(10,2) NOT NULL,
    transaction_status character varying(20) DEFAULT 'proposed'::character varying NOT NULL,
    proposed_timestamp timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    agreed_timestamp timestamp with time zone,
    completed_timestamp timestamp with time zone,
    transaction_data jsonb,
    session_id uuid NOT NULL,
    proposer_id uuid,
    recipient_id uuid,
    offer_type character varying(10),
    short_id character varying(20),
    CONSTRAINT no_self_trading CHECK ((seller_id <> buyer_id)),
    CONSTRAINT transactions_offer_type_check CHECK (((offer_type)::text = ANY (ARRAY[('buy'::character varying)::text, ('sell'::character varying)::text]))),
    CONSTRAINT transactions_transaction_status_check CHECK (((transaction_status)::text = ANY (ARRAY[('proposed'::character varying)::text, ('negotiating'::character varying)::text, ('agreed'::character varying)::text, ('completed'::character varying)::text, ('cancelled'::character varying)::text]))),
    CONSTRAINT valid_transaction_timing CHECK ((((agreed_timestamp IS NULL) OR (agreed_timestamp >= proposed_timestamp)) AND ((completed_timestamp IS NULL) OR (completed_timestamp >= agreed_timestamp))))
);


ALTER TABLE public.transactions OWNER TO postgres;

--
-- Name: wordguessing_chat_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.wordguessing_chat_history (
    chat_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    session_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    guess_text text NOT NULL,
    is_correct boolean NOT NULL,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    round_number integer DEFAULT 1
);


ALTER TABLE public.wordguessing_chat_history OWNER TO postgres;

--
-- Name: TABLE wordguessing_chat_history; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.wordguessing_chat_history IS 'Stores chat history for wordguessing experiment with guesses and correctness';


--
-- Name: mturk_tasks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mturk_tasks ALTER COLUMN id SET DEFAULT nextval('public.mturk_tasks_id_seq'::regclass);


--
-- Name: ai_agent_logs ai_agent_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_agent_logs
    ADD CONSTRAINT ai_agent_logs_pkey PRIMARY KEY (log_id);


--
-- Name: dashboard_notifications dashboard_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dashboard_notifications
    ADD CONSTRAINT dashboard_notifications_pkey PRIMARY KEY (notification_id);


--
-- Name: essay_assignments essay_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.essay_assignments
    ADD CONSTRAINT essay_assignments_pkey PRIMARY KEY (assignment_id);


--
-- Name: essay_assignments essay_assignments_session_id_essay_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.essay_assignments
    ADD CONSTRAINT essay_assignments_session_id_essay_id_key UNIQUE (session_id, essay_id);


--
-- Name: investments investments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investments
    ADD CONSTRAINT investments_pkey PRIMARY KEY (invest_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (message_id);


--
-- Name: mturk_tasks mturk_tasks_hit_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mturk_tasks
    ADD CONSTRAINT mturk_tasks_hit_id_key UNIQUE (hit_id);


--
-- Name: mturk_tasks mturk_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mturk_tasks
    ADD CONSTRAINT mturk_tasks_pkey PRIMARY KEY (id);


--
-- Name: participant_orders participant_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_orders
    ADD CONSTRAINT participant_orders_pkey PRIMARY KEY (order_id);


--
-- Name: participant_orders participant_orders_session_id_participant_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_orders
    ADD CONSTRAINT participant_orders_session_id_participant_id_key UNIQUE (session_id, participant_id);


--
-- Name: participant_status_log participant_status_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_status_log
    ADD CONSTRAINT participant_status_log_pkey PRIMARY KEY (status_log_id);


--
-- Name: participants participants_mturk_assignment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_mturk_assignment_id_key UNIQUE (mturk_assignment_id);


--
-- Name: participants participants_mturk_worker_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_mturk_worker_id_key UNIQUE (mturk_worker_id);


--
-- Name: participants participants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_pkey PRIMARY KEY (participant_id);


--
-- Name: participants participants_session_code_participant_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_session_code_participant_code_key UNIQUE (session_code, participant_code);


--
-- Name: participants participants_session_id_color_shape_combination_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_session_id_color_shape_combination_key UNIQUE (session_id, color_shape_combination);


--
-- Name: participants participants_session_id_participant_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_session_id_participant_code_key UNIQUE (session_id, participant_code);


--
-- Name: production_queue production_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.production_queue
    ADD CONSTRAINT production_queue_pkey PRIMARY KEY (queue_id);


--
-- Name: ranking_submissions ranking_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranking_submissions
    ADD CONSTRAINT ranking_submissions_pkey PRIMARY KEY (submission_id);


--
-- Name: research_observations research_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.research_observations
    ADD CONSTRAINT research_observations_pkey PRIMARY KEY (observation_id);


--
-- Name: schema_version schema_version_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.schema_version
    ADD CONSTRAINT schema_version_pkey PRIMARY KEY (version);


--
-- Name: session_analytics session_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_analytics
    ADD CONSTRAINT session_analytics_pkey PRIMARY KEY (analytics_id);


--
-- Name: session_analytics session_analytics_session_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_analytics
    ADD CONSTRAINT session_analytics_session_id_key UNIQUE (session_id);


--
-- Name: session_metrics_realtime session_metrics_realtime_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_metrics_realtime
    ADD CONSTRAINT session_metrics_realtime_pkey PRIMARY KEY (session_id);


--
-- Name: session_templates session_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_templates
    ADD CONSTRAINT session_templates_pkey PRIMARY KEY (template_id);


--
-- Name: session_templates session_templates_session_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_templates
    ADD CONSTRAINT session_templates_session_id_key UNIQUE (session_id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (session_id);


--
-- Name: sessions sessions_session_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_session_code_key UNIQUE (session_code);


--
-- Name: sessions sessions_short_id_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_short_id_unique UNIQUE (short_id);


--
-- Name: shape_inventory shape_inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shape_inventory
    ADD CONSTRAINT shape_inventory_pkey PRIMARY KEY (inventory_id);


--
-- Name: shape_inventory shape_inventory_session_id_participant_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shape_inventory
    ADD CONSTRAINT shape_inventory_session_id_participant_id_key UNIQUE (session_id, participant_id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: transactions transactions_short_id_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_short_id_unique UNIQUE (short_id);


--
-- Name: wordguessing_chat_history wordguessing_chat_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wordguessing_chat_history
    ADD CONSTRAINT wordguessing_chat_history_pkey PRIMARY KEY (chat_id);


--
-- Name: idx_ai_logs_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ai_logs_participant ON public.ai_agent_logs USING btree (participant_id);


--
-- Name: idx_ai_logs_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ai_logs_session ON public.ai_agent_logs USING btree (session_id);


--
-- Name: idx_ai_logs_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ai_logs_timestamp ON public.ai_agent_logs USING btree (log_timestamp);


--
-- Name: idx_essay_assignments_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_essay_assignments_session ON public.essay_assignments USING btree (session_id);


--
-- Name: idx_inventory_session_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inventory_session_participant ON public.shape_inventory USING btree (session_id, participant_id);


--
-- Name: idx_investments_decision_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_investments_decision_type ON public.investments USING btree (invest_decision_type);


--
-- Name: idx_investments_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_investments_participant ON public.investments USING btree (participant_id);


--
-- Name: idx_investments_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_investments_session ON public.investments USING btree (session_id);


--
-- Name: idx_investments_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_investments_timestamp ON public.investments USING btree (invest_timestamp);


--
-- Name: idx_messages_recipient; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_recipient ON public.messages USING btree (recipient_id);


--
-- Name: idx_messages_sender; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_sender ON public.messages USING btree (sender_id);


--
-- Name: idx_messages_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_session ON public.messages USING btree (session_id);


--
-- Name: idx_messages_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_timestamp ON public.messages USING btree (message_timestamp);


--
-- Name: idx_messages_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_type ON public.messages USING btree (message_type);


--
-- Name: idx_notifications_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notifications_created ON public.dashboard_notifications USING btree (created_at);


--
-- Name: idx_notifications_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notifications_session ON public.dashboard_notifications USING btree (session_id);


--
-- Name: idx_notifications_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notifications_type ON public.dashboard_notifications USING btree (notification_type);


--
-- Name: idx_notifications_undelivered; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_notifications_undelivered ON public.dashboard_notifications USING btree (delivered_to_dashboard) WHERE (delivered_to_dashboard = false);


--
-- Name: idx_observations_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_observations_session ON public.research_observations USING btree (session_id);


--
-- Name: idx_observations_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_observations_timestamp ON public.research_observations USING btree (observation_timestamp);


--
-- Name: idx_orders_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_participant ON public.participant_orders USING btree (participant_id);


--
-- Name: idx_orders_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_session ON public.participant_orders USING btree (session_id);


--
-- Name: idx_participants_agent_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_agent_type ON public.participants USING btree (agent_type);


--
-- Name: idx_participants_code_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_code_session ON public.participants USING btree (participant_code, session_code);


--
-- Name: idx_participants_is_agent; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_is_agent ON public.participants USING btree (is_agent);


--
-- Name: idx_participants_mbti_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_mbti_type ON public.participants USING btree (mbti_type);


--
-- Name: idx_participants_money; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_money ON public.participants USING btree (money);


--
-- Name: idx_participants_orders; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_orders ON public.participants USING gin (orders);


--
-- Name: idx_participants_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_session ON public.participants USING btree (session_id);


--
-- Name: idx_participants_session_activity; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_session_activity ON public.participants USING btree (session_id, last_activity_timestamp DESC NULLS LAST);


--
-- Name: idx_participants_session_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_session_code ON public.participants USING btree (session_code);


--
-- Name: idx_participants_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_status ON public.participants USING btree (login_status);


--
-- Name: idx_participants_tag; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_tag ON public.participants USING btree (tag);


--
-- Name: idx_participants_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_participants_type ON public.participants USING btree (participant_type);


--
-- Name: idx_production_queue_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_production_queue_participant ON public.production_queue USING btree (participant_id);


--
-- Name: idx_ranking_submissions_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ranking_submissions_participant ON public.ranking_submissions USING btree (participant_id);


--
-- Name: idx_ranking_submissions_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ranking_submissions_session ON public.ranking_submissions USING btree (session_id);


--
-- Name: idx_ranking_submissions_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ranking_submissions_timestamp ON public.ranking_submissions USING btree (submission_timestamp);


--
-- Name: idx_session_templates_default; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_session_templates_default ON public.session_templates USING btree (is_default) WHERE (is_default = true);


--
-- Name: idx_session_templates_researcher; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_session_templates_researcher ON public.session_templates USING btree (researcher_id);


--
-- Name: idx_session_templates_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_session_templates_session_id ON public.session_templates USING btree (session_id);


--
-- Name: idx_sessions_researcher; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_researcher ON public.sessions USING btree (researcher_id);


--
-- Name: idx_sessions_short_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_short_id ON public.sessions USING btree (short_id);


--
-- Name: idx_sessions_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_status ON public.sessions USING btree (session_status);


--
-- Name: idx_status_log_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_status_log_participant ON public.participant_status_log USING btree (participant_id);


--
-- Name: idx_status_log_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_status_log_session ON public.participant_status_log USING btree (session_id);


--
-- Name: idx_status_log_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_status_log_timestamp ON public.participant_status_log USING btree (status_change_timestamp);


--
-- Name: idx_transactions_buyer; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_buyer ON public.transactions USING btree (buyer_id);


--
-- Name: idx_transactions_seller; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_seller ON public.transactions USING btree (seller_id);


--
-- Name: idx_transactions_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_session ON public.transactions USING btree (session_id);


--
-- Name: idx_transactions_session_short_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_session_short_id ON public.transactions USING btree (session_id, short_id);


--
-- Name: idx_transactions_session_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_session_status ON public.transactions USING btree (session_id, transaction_status);


--
-- Name: idx_transactions_short_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_short_id ON public.transactions USING btree (short_id);


--
-- Name: idx_transactions_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_status ON public.transactions USING btree (transaction_status);


--
-- Name: idx_transactions_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_transactions_timestamp ON public.transactions USING btree (proposed_timestamp);


--
-- Name: idx_wordguessing_chat_participant; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wordguessing_chat_participant ON public.wordguessing_chat_history USING btree (participant_id);


--
-- Name: idx_wordguessing_chat_round; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wordguessing_chat_round ON public.wordguessing_chat_history USING btree (round_number);


--
-- Name: idx_wordguessing_chat_session; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wordguessing_chat_session ON public.wordguessing_chat_history USING btree (session_id);


--
-- Name: idx_wordguessing_chat_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wordguessing_chat_timestamp ON public.wordguessing_chat_history USING btree ("timestamp");


--
-- Name: messages trigger_new_message; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_new_message AFTER INSERT ON public.messages FOR EACH ROW EXECUTE FUNCTION public.notify_new_message();


--
-- Name: transactions trigger_new_transaction; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_new_transaction AFTER INSERT ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.notify_new_transaction();


--
-- Name: participants trigger_participant_status_change; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_participant_status_change AFTER UPDATE OF login_status ON public.participants FOR EACH ROW EXECUTE FUNCTION public.notify_participant_status_change();


--
-- Name: sessions trigger_set_session_short_id; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_set_session_short_id BEFORE INSERT ON public.sessions FOR EACH ROW EXECUTE FUNCTION public.set_session_short_id();


--
-- Name: transactions trigger_set_transaction_short_id; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_set_transaction_short_id BEFORE INSERT ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.set_transaction_short_id();


--
-- Name: messages trigger_update_activity; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trigger_update_activity AFTER INSERT ON public.messages FOR EACH ROW EXECUTE FUNCTION public.update_participant_activity();


--
-- Name: investments update_investments_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_investments_updated_at BEFORE UPDATE ON public.investments FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: session_templates update_session_templates_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_session_templates_updated_at BEFORE UPDATE ON public.session_templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_agent_logs ai_agent_logs_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_agent_logs
    ADD CONSTRAINT ai_agent_logs_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: ai_agent_logs ai_agent_logs_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_agent_logs
    ADD CONSTRAINT ai_agent_logs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: dashboard_notifications dashboard_notifications_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dashboard_notifications
    ADD CONSTRAINT dashboard_notifications_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: essay_assignments essay_assignments_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.essay_assignments
    ADD CONSTRAINT essay_assignments_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: investments investments_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investments
    ADD CONSTRAINT investments_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: investments investments_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.investments
    ADD CONSTRAINT investments_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: messages messages_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: messages messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: messages messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: mturk_tasks mturk_tasks_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mturk_tasks
    ADD CONSTRAINT mturk_tasks_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: participant_orders participant_orders_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_orders
    ADD CONSTRAINT participant_orders_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: participant_orders participant_orders_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_orders
    ADD CONSTRAINT participant_orders_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: participant_status_log participant_status_log_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_status_log
    ADD CONSTRAINT participant_status_log_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: participant_status_log participant_status_log_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participant_status_log
    ADD CONSTRAINT participant_status_log_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: participants participants_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: production_queue production_queue_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.production_queue
    ADD CONSTRAINT production_queue_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: ranking_submissions ranking_submissions_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranking_submissions
    ADD CONSTRAINT ranking_submissions_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: ranking_submissions ranking_submissions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ranking_submissions
    ADD CONSTRAINT ranking_submissions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: research_observations research_observations_related_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.research_observations
    ADD CONSTRAINT research_observations_related_participant_id_fkey FOREIGN KEY (related_participant_id) REFERENCES public.participants(participant_id) ON DELETE SET NULL;


--
-- Name: research_observations research_observations_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.research_observations
    ADD CONSTRAINT research_observations_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: session_analytics session_analytics_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_analytics
    ADD CONSTRAINT session_analytics_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: session_metrics_realtime session_metrics_realtime_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_metrics_realtime
    ADD CONSTRAINT session_metrics_realtime_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: shape_inventory shape_inventory_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shape_inventory
    ADD CONSTRAINT shape_inventory_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: shape_inventory shape_inventory_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shape_inventory
    ADD CONSTRAINT shape_inventory_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: transactions transactions_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: transactions transactions_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: transactions transactions_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- Name: wordguessing_chat_history wordguessing_chat_history_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wordguessing_chat_history
    ADD CONSTRAINT wordguessing_chat_history_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(participant_id) ON DELETE CASCADE;


--
-- Name: wordguessing_chat_history wordguessing_chat_history_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wordguessing_chat_history
    ADD CONSTRAINT wordguessing_chat_history_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(session_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict FbfWS1zFxrQIIPXIuD5aa2luRUo9S0K2ifpzhLL4JugQ54rmHmU8ERrvnGXMfd8

