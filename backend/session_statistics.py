#!/usr/bin/env python3
"""
Session Statistics Extractor
Extracts comprehensive statistics for Shape Factory research sessions
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from decimal import Decimal
import json
import csv
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import argparse

# Load environment variables
load_dotenv()

@dataclass
class ParticipantStats:
    """Individual participant statistics"""
    participant_id: str
    participant_code: str
    participant_type: str
    specialty_shape: str
    login_status: str
    
    # Final wealth
    final_wealth: float = 0.0
    
    # Trade statistics
    number_successful_trades: int = 0
    average_trade_price: float = 0.0
    minimum_trade_price: float = 0.0
    maximum_trade_price: float = 0.0
    
    # Message statistics
    number_messages: int = 0
    average_message_length: float = 0.0
    average_response_time: float = 0.0
    average_messages_between_trades: float = 0.0
    
    def __post_init__(self):
        pass

@dataclass
class SessionStatistics:
    """Overall session statistics"""
    session_code: str
    session_id: str
    total_participants: int = 0
    human_participants: int = 0
    ai_participants: int = 0
    
    # Session Outcome
    highest_wealth: float = 0.0
    highest_wealth_participant: str = ""
    lowest_wealth: float = 0.0
    lowest_wealth_participant: str = ""
    
    # Comprehensive Statistics (All Users)
    average_wealth: float = 0.0
    total_successful_trades: int = 0
    average_successful_trades: float = 0.0
    average_trade_price: float = 0.0
    minimum_trade_price: float = 0.0
    maximum_trade_price: float = 0.0
    
    # Message Statistics
    total_messages: int = 0
    average_messages_per_user: float = 0.0
    average_message_length_per_user: float = 0.0
    average_message_length_per_human: float = 0.0
    average_message_response_latency_per_user: float = 0.0
    average_messages_per_trade: float = 0.0
    
    # Participant details
    participants: List[ParticipantStats] = None
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []

@dataclass
class ParticipantSessionStats:
    """Combined participant and session statistics for CSV export"""
    session_id: str
    session_code: str
    participant_id: str
    participant_code: str
    participant_type: str
    specialty_shape: str
    login_status: str
    
    # Participant statistics
    final_wealth: float = 0.0
    number_successful_trades: int = 0
    average_trade_price: float = 0.0
    minimum_trade_price: float = 0.0
    maximum_trade_price: float = 0.0
    number_messages: int = 0
    average_message_length: float = 0.0
    average_response_time: float = 0.0
    average_messages_between_trades: float = 0.0
    
    # Session statistics
    session_total_participants: int = 0
    session_human_participants: int = 0
    session_ai_participants: int = 0
    session_highest_wealth: float = 0.0
    session_lowest_wealth: float = 0.0
    session_average_wealth: float = 0.0
    session_total_successful_trades: int = 0
    session_average_successful_trades: float = 0.0
    session_average_trade_price: float = 0.0
    session_minimum_trade_price: float = 0.0
    session_maximum_trade_price: float = 0.0
    session_total_messages: int = 0
    session_average_messages_per_user: float = 0.0
    session_average_message_length_per_user: float = 0.0
    session_average_message_length_per_human: float = 0.0
    session_average_message_response_latency_per_user: float = 0.0
    session_average_messages_per_trade: float = 0.0

class SessionStatisticsExtractor:
    """Extract comprehensive session statistics from the database"""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database connection"""
        if database_url is None:
            database_url = f"postgresql://{os.getenv('DATABASE_USER', '')}:{os.getenv('DATABASE_PASSWORD', '')}@{os.getenv('DATABASE_HOST', 'localhost')}:{os.getenv('DATABASE_PORT', '5432')}/{os.getenv('DATABASE_NAME', 'shape_factory_research')}"
        
        self.database_url = database_url
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            print(f"✅ Connected to database")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✅ Database connection closed")
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get basic session information by session ID (UUID)"""
        query = """
        SELECT session_id, session_code, experiment_type, session_status,
               created_at, setup_started_at, session_started_at, session_completed_at,
               experiment_config
        FROM sessions 
        WHERE session_id = %s
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id,))
            result = cur.fetchone()
            
        if not result:
            raise ValueError(f"Session '{session_id}' not found")
        
        return dict(result)
    
    def get_session_info_by_code(self, session_code: str) -> Dict[str, Any]:
        """Get basic session information by session code (readable)"""
        query = """
        SELECT session_id, session_code, experiment_type, session_status,
               created_at, setup_started_at, session_started_at, session_completed_at,
               experiment_config
        FROM sessions 
        WHERE session_code = %s
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_code,))
            result = cur.fetchone()
            
        if not result:
            raise ValueError(f"Session '{session_code}' not found")
        
        return dict(result)
    
    def get_participant_info_by_name(self, session_code: str, participant_name: str) -> Dict[str, Any]:
        """Get specific participant information by session code and participant name (readable)"""
        query = """
        SELECT p.participant_id, p.participant_code, p.participant_type, 
               p.specialty_shape, p.login_status, p.login_timestamp,
               p.money
        FROM participants p
        JOIN sessions s ON p.session_id = s.session_id
        WHERE s.session_code = %s AND p.participant_code = %s
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_code, participant_name))
            result = cur.fetchone()
            
        if not result:
            raise ValueError(f"Participant '{participant_name}' not found in session '{session_code}'")
        
        return dict(result)
    
    def get_participant_info(self, session_id: str, participant_id: str) -> Dict[str, Any]:
        """Get specific participant information by session ID and participant ID (UUIDs)"""
        query = """
        SELECT participant_id, participant_code, participant_type, 
               specialty_shape, login_status, login_timestamp,
               money
        FROM participants 
        WHERE session_id = %s AND participant_id = %s
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id, participant_id))
            result = cur.fetchone()
            
        if not result:
            raise ValueError(f"Participant '{participant_id}' not found in session '{session_id}'")
        
        return dict(result)
    
    def get_participants(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all participants for a session"""
        query = """
        SELECT participant_id, participant_code, participant_type, 
               specialty_shape, login_status, login_timestamp,
               money
        FROM participants 
        WHERE session_id = %s
        ORDER BY participant_code
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_trades(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all successful trades for a session"""
        query = """
        SELECT t.transaction_id, t.seller_id, t.buyer_id, t.shape_type,
               t.quantity, t.agreed_price, t.transaction_status,
               t.proposed_timestamp, t.agreed_timestamp, t.completed_timestamp,
               p1.participant_code as seller_code,
               p2.participant_code as buyer_code
        FROM transactions t
        JOIN participants p1 ON t.seller_id = p1.participant_id
        JOIN participants p2 ON t.buyer_id = p2.participant_id
        WHERE t.session_id = %s AND t.transaction_status = 'completed'
        ORDER BY t.completed_timestamp
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session"""
        query = """
        SELECT m.message_id, m.sender_id, m.recipient_id, m.message_type,
               m.message_content, m.message_timestamp,
               p1.participant_code as sender_code,
               p2.participant_code as recipient_code
        FROM messages m
        JOIN participants p1 ON m.sender_id = p1.participant_id
        LEFT JOIN participants p2 ON m.recipient_id = p2.participant_id
        WHERE m.session_id = %s
        ORDER BY m.message_timestamp
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_participant_money(self, session_id: str) -> Dict[str, float]:
        """Get current money for each participant from the actual database"""
        query = """
        SELECT p.participant_code, p.money as current_money
        FROM participants p
        WHERE p.session_id = %s
        """
        
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (session_id,))
            results = cur.fetchall()
            
        money_dict = {}
        for row in results:
            money_dict[row['participant_code']] = float(row['current_money']) if row['current_money'] else 300.0
        
        return money_dict
    
    def calculate_messages_between_trades(self, participant_id: str, trades: List[Dict[str, Any]], 
                                        messages: List[Dict[str, Any]]) -> float:
        """Calculate average messages sent between consecutive trades for a participant"""
        participant_trades = [t for t in trades if t['seller_id'] == participant_id or t['buyer_id'] == participant_id]
        
        if not participant_trades:
            return 0.0
        
        # Sort trades by completion time
        participant_trades.sort(key=lambda t: t['completed_timestamp'])
        
        total_messages_between_trades = 0
        trade_intervals = 0
        
        for i in range(1, len(participant_trades)):
            current_trade = participant_trades[i]
            previous_trade = participant_trades[i-1]
            
            # Find messages between the last trade and current trade
            start_time = previous_trade['completed_timestamp']
            end_time = current_trade['completed_timestamp']
            
            # Count messages sent by this participant to any other participant in this time interval
            messages_between_trades = [
                m for m in messages 
                if m['sender_id'] == participant_id 
                and m['message_timestamp'] > start_time
                and m['message_timestamp'] <= end_time
            ]
            
            total_messages_between_trades += len(messages_between_trades)
            trade_intervals += 1
        
        # Return average messages between trades
        return total_messages_between_trades / trade_intervals if trade_intervals > 0 else 0.0
    
    def calculate_participant_stats(self, participant_data: Dict[str, Any], 
                                  trades: List[Dict[str, Any]], 
                                  messages: List[Dict[str, Any]],
                                  current_money: float) -> ParticipantStats:
        """Calculate statistics for a single participant"""
        
        participant_id = participant_data['participant_id']
        participant_code = participant_data['participant_code']
        
        # Initialize participant stats
        stats = ParticipantStats(
            participant_id=participant_id,
            participant_code=participant_code,
            participant_type=participant_data['participant_type'],
            specialty_shape=participant_data['specialty_shape'],
            login_status=participant_data['login_status'],
            final_wealth=current_money
        )
        
        # Calculate trade statistics
        participant_trades = [t for t in trades if t['seller_id'] == participant_id or t['buyer_id'] == participant_id]
        stats.number_successful_trades = len(participant_trades)
        
        if participant_trades:
            # Calculate trade prices for this participant
            trade_prices = []
            for trade in participant_trades:
                trade_prices.append(float(trade['agreed_price']))
            
            if trade_prices:
                stats.average_trade_price = sum(trade_prices) / len(trade_prices)
                stats.minimum_trade_price = min(trade_prices)
                stats.maximum_trade_price = max(trade_prices)
        
        # Calculate message statistics
        sent_messages = [m for m in messages if m['sender_id'] == participant_id]
        stats.number_messages = len(sent_messages)
        
        if sent_messages:
            total_length = sum(len(m['message_content']) for m in sent_messages)
            stats.average_message_length = total_length / len(sent_messages)
        
        # Calculate average response time (from received message to response)
        if len(sent_messages) > 0:
            # Get all messages received by this participant
            received_messages = [m for m in messages if m['recipient_id'] == participant_id]
            
            if received_messages:
                response_times = []
                
                for received_msg in received_messages:
                    # Find the next message sent by this participant after receiving the message
                    received_time = received_msg['message_timestamp']
                    
                    # Look for the next message sent by this participant
                    next_sent_message = None
                    for sent_msg in sent_messages:
                        if sent_msg['message_timestamp'] > received_time:
                            if next_sent_message is None or sent_msg['message_timestamp'] < next_sent_message['message_timestamp']:
                                next_sent_message = sent_msg
                    
                    # If we found a response, calculate the response time
                    if next_sent_message:
                        response_time = (next_sent_message['message_timestamp'] - received_time).total_seconds()
                        if response_time < 300:  # Only count responses within 5 minutes
                            response_times.append(response_time)
                
                if response_times:
                    stats.average_response_time = sum(response_times) / len(response_times)
        
        # Calculate average messages between trades
        stats.average_messages_between_trades = self.calculate_messages_between_trades(participant_id, trades, messages)
        
        return stats
    
    def extract_session_statistics(self, session_code: str) -> SessionStatistics:
        """Extract comprehensive statistics for a session"""
        
        print(f"📊 Extracting statistics for session: {session_code}")
        
        # Get session information
        session_info = self.get_session_info_by_code(session_code)
        session_id = session_info['session_id']
        
        # Initialize session statistics
        stats = SessionStatistics(
            session_code=session_code,
            session_id=session_id
        )
        
        # Get all data
        participants_data = self.get_participants(session_id)
        trades = self.get_trades(session_id)
        messages = self.get_messages(session_id)
        participant_money = self.get_participant_money(session_id)
        
        # Calculate participant statistics
        for participant_data in participants_data:
            participant_code = participant_data['participant_code']
            current_money = participant_money.get(participant_code, 300.0)
            
            participant_stats = self.calculate_participant_stats(
                participant_data, trades, messages, current_money
            )
            stats.participants.append(participant_stats)
        
        # Calculate overall statistics
        stats.total_participants = len(stats.participants)
        stats.human_participants = len([p for p in stats.participants if p.participant_type == 'human'])
        stats.ai_participants = len([p for p in stats.participants if p.participant_type == 'ai_agent'])
        
        # Session Outcome: Highest/Lowest Wealth
        if stats.participants:
            wealth_values = [p.final_wealth for p in stats.participants]
            stats.highest_wealth = max(wealth_values)
            stats.lowest_wealth = min(wealth_values)
            
            # Find participants with highest and lowest wealth
            highest_wealth_participant = max(stats.participants, key=lambda p: p.final_wealth)
            lowest_wealth_participant = min(stats.participants, key=lambda p: p.final_wealth)
            stats.highest_wealth_participant = highest_wealth_participant.participant_code
            stats.lowest_wealth_participant = lowest_wealth_participant.participant_code
        
        # Comprehensive Statistics (All Users)
        if stats.participants:
            stats.average_wealth = sum(p.final_wealth for p in stats.participants) / len(stats.participants)
            stats.total_successful_trades = sum(p.number_successful_trades for p in stats.participants)
            stats.average_successful_trades = stats.total_successful_trades / len(stats.participants)
        
        if trades:
            trade_prices = [float(t['agreed_price']) for t in trades]
            stats.average_trade_price = sum(trade_prices) / len(trade_prices)
            stats.minimum_trade_price = min(trade_prices)
            stats.maximum_trade_price = max(trade_prices)
        
        # Message Statistics
        stats.total_messages = len(messages)
        if stats.total_participants > 0:
            stats.average_messages_per_user = stats.total_messages / stats.total_participants
        
        human_participants = [p for p in stats.participants if p.participant_type == 'human']
        
        if messages:
            # Calculate average message length per user (all messages)
            total_length = sum(len(m['message_content']) for m in messages)
            stats.average_message_length_per_user = total_length / len(messages)
            
            # Calculate average message length per human (only messages sent by humans)
            human_messages = [m for m in messages if m['sender_id'] in [p.participant_id for p in stats.participants if p.participant_type == 'human']]
            if human_messages:
                human_total_length = sum(len(m['message_content']) for m in human_messages)
                stats.average_message_length_per_human = human_total_length / len(human_messages)
            
            # Calculate average message response time per user
            all_response_times = [p.average_response_time for p in stats.participants if p.average_response_time > 0]
            if all_response_times:
                stats.average_message_response_latency_per_user = sum(all_response_times) / len(all_response_times)
        
        # Calculate average messages per trade
        if stats.total_successful_trades > 0:
            stats.average_messages_per_trade = stats.total_messages / stats.total_successful_trades
        
        return stats
    
    def extract_participant_statistics_by_name(self, session_code: str, participant_name: str) -> Tuple[ParticipantStats, SessionStatistics]:
        """Extract statistics for a specific participant by session code and participant name (readable)"""
        
        print(f"📊 Extracting statistics for participant '{participant_name}' in session '{session_code}'")
        
        # Get participant information
        participant_data = self.get_participant_info_by_name(session_code, participant_name)
        participant_id = participant_data['participant_id']
        
        # Get session information
        session_info = self.get_session_info_by_code(session_code)
        session_id = session_info['session_id']
        
        # Get session data
        trades = self.get_trades(session_id)
        messages = self.get_messages(session_id)
        participant_money = self.get_participant_money(session_id)
        
        # Calculate participant statistics
        participant_code = participant_data['participant_code']
        current_money = participant_money.get(participant_code, 300.0)
        
        participant_stats = self.calculate_participant_stats(
            participant_data, trades, messages, current_money
        )
        
        # Get full session statistics
        session_stats = self.extract_session_statistics(session_code)
        
        return participant_stats, session_stats
    
    def extract_participant_statistics(self, session_id: str, participant_id: str) -> Tuple[ParticipantStats, SessionStatistics]:
        """Extract statistics for a specific participant in a specific session by UUIDs"""
        
        print(f"📊 Extracting statistics for participant {participant_id} in session {session_id}")
        
        # Get session information
        session_info = self.get_session_info(session_id)
        session_code = session_info['session_code']
        
        # Get participant information
        participant_data = self.get_participant_info(session_id, participant_id)
        
        # Get session data
        trades = self.get_trades(session_id)
        messages = self.get_messages(session_id)
        participant_money = self.get_participant_money(session_id)
        
        # Calculate participant statistics
        participant_code = participant_data['participant_code']
        current_money = participant_money.get(participant_code, 300.0)
        
        participant_stats = self.calculate_participant_stats(
            participant_data, trades, messages, current_money
        )
        
        # Get full session statistics
        session_stats = self.extract_session_statistics(session_code)
        
        return participant_stats, session_stats
    
    def export_participant_to_json(self, participant_stats: ParticipantStats, session_stats: SessionStatistics, 
                                  output_file: str):
        """Export specific participant statistics to JSON file"""
        
        def datetime_converter(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        # Create combined data structure
        export_data = {
            "participant": asdict(participant_stats),
            "session_context": {
                "session_code": session_stats.session_code,
                "session_id": session_stats.session_id,
                "total_participants": session_stats.total_participants,
                "human_participants": session_stats.human_participants,
                "ai_participants": session_stats.ai_participants,
                "session_highest_wealth": session_stats.highest_wealth,
                "session_lowest_wealth": session_stats.lowest_wealth,
                "session_average_wealth": session_stats.average_wealth,
                "session_total_trades": session_stats.total_successful_trades,
                "session_average_trade_price": session_stats.average_trade_price,
                "session_total_messages": session_stats.total_messages
            }
        }
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=datetime_converter, ensure_ascii=False)
        
        print(f"✅ Participant statistics exported to: {output_file}")
    
    def export_multiple_to_csv(self, session_participant_pairs: List[Tuple[str, str]], output_file: str):
        """Export statistics for multiple session-participant pairs to CSV"""
        
        print(f"📊 Exporting statistics for {len(session_participant_pairs)} session-participant pairs to CSV")
        
        all_stats = []
        
        for i, (session_code, participant_name) in enumerate(session_participant_pairs, 1):
            try:
                print(f"Processing {i}/{len(session_participant_pairs)}: Session '{session_code}', Participant '{participant_name}'")
                
                # Extract statistics using readable identifiers
                participant_stats, session_stats = self.extract_participant_statistics_by_name(session_code, participant_name)
                
                # Create combined stats object
                combined_stats = ParticipantSessionStats(
                    session_id=session_stats.session_id,
                    session_code=session_code,
                    participant_id=participant_stats.participant_id,
                    participant_code=participant_name,
                    participant_type=participant_stats.participant_type,
                    specialty_shape=participant_stats.specialty_shape,
                    login_status=participant_stats.login_status,
                    
                    # Participant statistics
                    final_wealth=participant_stats.final_wealth,
                    number_successful_trades=participant_stats.number_successful_trades,
                    average_trade_price=participant_stats.average_trade_price,
                    minimum_trade_price=participant_stats.minimum_trade_price,
                    maximum_trade_price=participant_stats.maximum_trade_price,
                    number_messages=participant_stats.number_messages,
                    average_message_length=participant_stats.average_message_length,
                    average_response_time=participant_stats.average_response_time,
                    average_messages_between_trades=participant_stats.average_messages_between_trades,
                    
                    # Session statistics
                    session_total_participants=session_stats.total_participants,
                    session_human_participants=session_stats.human_participants,
                    session_ai_participants=session_stats.ai_participants,
                    session_highest_wealth=session_stats.highest_wealth,
                    session_lowest_wealth=session_stats.lowest_wealth,
                    session_average_wealth=session_stats.average_wealth,
                    session_total_successful_trades=session_stats.total_successful_trades,
                    session_average_successful_trades=session_stats.average_successful_trades,
                    session_average_trade_price=session_stats.average_trade_price,
                    session_minimum_trade_price=session_stats.minimum_trade_price,
                    session_maximum_trade_price=session_stats.maximum_trade_price,
                    session_total_messages=session_stats.total_messages,
                    session_average_messages_per_user=session_stats.average_messages_per_user,
                    session_average_message_length_per_user=session_stats.average_message_length_per_user,
                    session_average_message_length_per_human=session_stats.average_message_length_per_human,
                    session_average_message_response_latency_per_user=session_stats.average_message_response_latency_per_user,
                    session_average_messages_per_trade=session_stats.average_messages_per_trade
                )
                
                all_stats.append(combined_stats)
                
            except Exception as e:
                print(f"❌ Error processing Session '{session_code}', Participant '{participant_name}': {e}")
                continue
        
        if not all_stats:
            print("❌ No statistics to export")
            return
        
        # Export to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(asdict(all_stats[0]).keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for stats in all_stats:
                writer.writerow(asdict(stats))
        
        print(f"✅ CSV export completed: {len(all_stats)} records written to {output_file}")
    
    def export_to_json(self, stats: SessionStatistics, output_file: str):
        """Export statistics to JSON file with proper datetime handling"""
        
        def datetime_converter(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        # Convert to dictionary
        stats_dict = asdict(stats)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, indent=2, default=datetime_converter, ensure_ascii=False)

def main():
    """Main function to run the statistics extractor"""
    
    parser = argparse.ArgumentParser(description='Extract session statistics from Shape Factory database')
    parser.add_argument('--session-code', help='Session code to analyze (e.g., SESSION123)')
    parser.add_argument('--session-id', help='Session ID (UUID) to analyze')
    parser.add_argument('--participant-name', help='Participant name to analyze (e.g., Alice)')
    parser.add_argument('--participant-id', help='Participant ID (UUID) to analyze (requires session-id)')
    parser.add_argument('--csv-input', help='CSV file with session_code,participant_name pairs for batch export')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--database-url', help='Database connection URL')
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = SessionStatisticsExtractor(args.database_url)
    
    try:
        # Connect to database
        extractor.connect()
        
        if args.csv_input:
            # Batch CSV export using readable identifiers
            import csv
            session_participant_pairs = []
            
            with open(args.csv_input, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    session_participant_pairs.append((row['session_code'], row['participant_name']))
            
            output_file = args.output or "batch_participant_statistics.csv"
            extractor.export_multiple_to_csv(session_participant_pairs, output_file)
            
        elif args.participant_name and args.session_code:
            # Individual participant export using readable identifiers
            participant_stats, session_stats = extractor.extract_participant_statistics_by_name(
                args.session_code, args.participant_name
            )
                    
            # Export to JSON
            output_file = args.output or f"participant_{args.participant_name}_session_{args.session_code}.json"
            extractor.export_participant_to_json(participant_stats, session_stats, output_file)
            
        elif args.participant_id and args.session_id:
            # Individual participant export using UUIDs (legacy support)
            participant_stats, session_stats = extractor.extract_participant_statistics(args.session_id, args.participant_id)
            
            # Export to JSON
            output_file = args.output or f"participant_{args.participant_id}_session_{args.session_id}.json"
            extractor.export_participant_to_json(participant_stats, session_stats, output_file)
            
        elif args.session_code:
            # Session analysis
            stats = extractor.extract_session_statistics(args.session_code)
            
            # Print summary
            # extractor.print_summary(stats)
            
            # Export to JSON
            output_file = args.output or f"session_{args.session_code}_statistics.json"
            extractor.export_to_json(stats, output_file)
            
        else:
            print("❌ Please specify either:")
            print("   --session-code for session analysis")
            print("   --session-code and --participant-name for individual participant export")
            print("   --session-id and --participant-id for UUID-based export (legacy)")
            print("   --csv-input for batch CSV export")
            return 1
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        extractor.disconnect()
    
    return 0

if __name__ == "__main__":
    exit(main())
