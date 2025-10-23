### ShapeFactory (most comprehensive)
- **Participant (private)**
  - money, inventory[], specialty_shape
  - orders[] (remaining), orders_completed, total_orders, completion_percentage
  - specialty_production_used, production_queue[{shape, quantity, status, time_remaining}]
- **Session/Public**
  - session_code, experiment_status (idle/running/paused/completed), time_remaining, round_duration_minutes
  - experiment_config: startingMoney, minTradePrice, maxTradePrice, specialtyCost, regularCost, productionTime, maxProductionNum, shapesPerOrder, numShapeTypes, awarenessDashboard
  - other_participants[{participant_code (display/internal), shape, status, money?, orders?, orders_completed?, completion_percentage?, specialty_production_used?}] (depends on awarenessDashboard)
- **Messaging**
  - unread/broadcast/direct messages[{message_id, sender_code, recipient_code/null, content, timestamp, delivered_status, message_type='chat'}]
- **Trading**
  - pending_offers_sent/received counts
  - detailed pending offers (proposed): {transaction_id/short_id, offer_type (buy/sell), shape_type, quantity, agreed_price, proposer_code, recipient_code, proposed_timestamp}
  - recent finished offers (completed/declined/cancelled): {short_id, recipient_code, offer_type, shape_type, quantity, agreed_price, completed_timestamp}
- **System/Derived**
  - timer-state override (via API), failure summaries (recent failed actions)

### DayTrader
- **Participant (private)**
  - money
- **Session/Public**
  - session_code, experiment_status, time_remaining, round_duration_minutes
  - experiment_config: minTradePrice, maxTradePrice, startingMoney
  - other_participants basic presence/status
- **Messaging**
  - unread direct/broadcast messages (same structure as above)
- **Trading**
  - invest (invest_id, invest_price, invest_type, invest_decision_type (individual/group)) (the invest can be seen as a simplified trade action, without agreement, shape_type, quantity, agreed_price, proposer_code, recipient_code. NO buy/sell, 'invest' is the only action.)
- **System/Derived**
  - timer-state override (via API), failure summaries (recent failed actions)

### EssayRanking
- **Participant (private)**
  - current_rankings[], submitted_rankings_count
- **Session/Public**
  - session_code, experiment_status, time_remaining, round_duration_minutes
  - experiment_config: assigned_essays[] (ids)
  - other_participants basic presence/status, progress (optional)
- **Messaging**
  - unread direct/broadcast messages (same structure as above)
- **Evaluation/Records**
  - timer-state override (via API), failure summaries (recent failed actions)

### WordGuessing
- **Participant (private)**
  - role (guesser/hinter), current_round, score, assigned_words (for hinter)
- **Session/Public**
  - session_code, experiment_status, time_remaining, round_duration_minutes
- **Messaging**
  - unread direct chat messages
- **Game State**
  - chat_history[{guess, correct?, timestamp}]

### Common fields across experiments
- **Session meta**: session_code, experiment_type, experiment_status, time_remaining, round_duration_minutes, experiment_config
- **Participant meta**: participant_code, participant_type (human/ai_agent), login_status, last_activity_timestamp
- **Messaging**: unified message schema with delivered_status and message_type='chat'
- **Others**: failure summaries (for agent feedback), other_participants list for awareness
