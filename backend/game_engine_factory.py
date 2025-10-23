#!/usr/bin/env python3
"""
Game Engine Factory
- Factory for creating experiment-specific game engines
- Provides unified interface for different experiment types
"""

from typing import Any, Dict, Optional
from game_engine import GameEngine
from daytrader_game_engine import DayTraderGameEngine
from essayranking_game_engine import EssayRankingGameEngine
from wordguessing_game_engine import WordGuessingGameEngine


class GameEngineFactory:
    """Factory for creating experiment-specific game engines"""
    
    # Class-level cache for game engine instances
    _engines = {}
    
    @staticmethod
    def create_game_engine(experiment_type: str, db_connection_string: str):
        """Create a game engine for the specified experiment type (singleton pattern)"""
        experiment_type = experiment_type.lower().strip()
        
        # Create a cache key based on experiment type and connection string
        cache_key = f"{experiment_type}_{hash(db_connection_string)}"
        
        # Return cached instance if it exists
        if cache_key in GameEngineFactory._engines:
            return GameEngineFactory._engines[cache_key]
        
        # Create new instance and cache it
        if experiment_type == "shapefactory":
            engine = GameEngine(db_connection_string)
        elif experiment_type == "daytrader":
            engine = DayTraderGameEngine(db_connection_string)
        elif experiment_type == "essayranking":
            engine = EssayRankingGameEngine(db_connection_string)
        elif experiment_type == "wordguessing":
            engine = WordGuessingGameEngine(db_connection_string)
        else:
            # Default to ShapeFactory for backward compatibility
            engine = GameEngine(db_connection_string)
        
        # Cache the engine instance
        GameEngineFactory._engines[cache_key] = engine
        return engine
    
    @staticmethod
    def get_supported_experiment_types() -> list:
        """Get list of supported experiment types"""
        return ["shapefactory", "daytrader", "essayranking", "wordguessing"]
    
    @staticmethod
    def is_experiment_type_supported(experiment_type: str) -> bool:
        """Check if an experiment type is supported"""
        return experiment_type.lower().strip() in GameEngineFactory.get_supported_experiment_types()
