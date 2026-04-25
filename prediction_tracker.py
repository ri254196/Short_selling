import sqlite3
import pandas as pd
from datetime import datetime, timedelta

class PredictionTracker:
    def __init__(self, db_path="predictions.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for tracking predictions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                oi_change REAL NOT NULL,
                price_change REAL NOT NULL,
                predicted_probability REAL NOT NULL,
                predicted_direction TEXT NOT NULL,
                actual_price REAL,
                actual_price_next_day REAL,
                actual_direction TEXT,
                is_correct INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create model_weights table for storing and adjusting model weights
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_weights (
                signal_type TEXT PRIMARY KEY,
                oi_weight REAL DEFAULT 0.6,
                price_weight REAL DEFAULT 0.4,
                total_predictions INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                win_ratio REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Initialize default weights
        cursor.execute('''
            INSERT OR IGNORE INTO model_weights (signal_type, oi_weight, price_weight)
            VALUES ('RISE_OI_SLIDE_PRICE', 0.6, 0.4)
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO model_weights (signal_type, oi_weight, price_weight)
            VALUES ('SLIDE_OI_SLIDE_PRICE', 0.5, 0.5)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_prediction(self, date, symbol, signal_type, oi_change, price_change, 
                      predicted_probability, actual_price):
        """Save a prediction to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        predicted_direction = "DOWN" if price_change < 0 else "UP"
        
        cursor.execute('''
            INSERT INTO predictions 
            (date, symbol, signal_type, oi_change, price_change, predicted_probability, 
             predicted_direction, actual_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date, symbol, signal_type, oi_change, price_change, predicted_probability,
              predicted_direction, actual_price))
        
        conn.commit()
        conn.close()
    
    def update_actual_price(self, date, symbol, actual_price_next_day):
        """Update the actual next-day price for a prediction"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the prediction
        cursor.execute('''
            SELECT id, actual_price, predicted_direction FROM predictions
            WHERE date = ? AND symbol = ? AND actual_price_next_day IS NULL
            ORDER BY id DESC LIMIT 1
        ''', (date, symbol))
        
        prediction = cursor.fetchone()
        
        if prediction:
            pred_id, actual_price, predicted_direction = prediction
            
            # Calculate actual direction
            actual_direction = "DOWN" if actual_price_next_day < actual_price else "UP"
            
            # Check if prediction was correct
            is_correct = 1 if actual_direction == predicted_direction else 0
            
            # Update the prediction
            cursor.execute('''
                UPDATE predictions
                SET actual_price_next_day = ?, actual_direction = ?, is_correct = ?
                WHERE id = ?
            ''', (actual_price_next_day, actual_direction, is_correct, pred_id))
            
            # Update model weights
            cursor.execute('''
                SELECT signal_type FROM predictions WHERE id = ?
            ''', (pred_id,))
            signal_type = cursor.fetchone()[0]
            
            self._update_model_weights(cursor, signal_type, is_correct)
            
            conn.commit()
        
        conn.close()
    
    def _update_model_weights(self, cursor, signal_type, is_correct):
        """Update model weights based on prediction accuracy"""
        # Get current weights
        cursor.execute('''
            SELECT oi_weight, price_weight, total_predictions, correct_predictions
            FROM model_weights WHERE signal_type = ?
        ''', (signal_type,))
        
        row = cursor.fetchone()
        if row:
            oi_weight, price_weight, total, correct = row
            
            # Update counts
            total += 1
            correct += is_correct
            
            # Calculate new win ratio
            win_ratio = correct / total if total > 0 else 0.0
            
            # Adjust weights based on performance
            # If win ratio < 50%, increase weight of the factor that worked better
            if win_ratio < 0.5:
                # Simple adjustment: if wrong, slightly rebalance weights
                adjustment = 0.05
                if is_correct == 0:
                    # Prediction was wrong, try to rebalance
                    if oi_weight > price_weight:
                        oi_weight -= adjustment
                        price_weight += adjustment
                    else:
                        oi_weight += adjustment
                        price_weight -= adjustment
            
            # Ensure weights stay within reasonable bounds
            oi_weight = max(0.3, min(0.7, oi_weight))
            price_weight = 1.0 - oi_weight
            
            # Update database
            cursor.execute('''
                UPDATE model_weights
                SET oi_weight = ?, price_weight = ?, total_predictions = ?,
                    correct_predictions = ?, win_ratio = ?, last_updated = CURRENT_TIMESTAMP
                WHERE signal_type = ?
            ''', (oi_weight, price_weight, total, correct, win_ratio, signal_type))
    
    def get_model_weights(self, signal_type):
        """Get current model weights for a signal type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT oi_weight, price_weight, win_ratio, total_predictions
            FROM model_weights WHERE signal_type = ?
        ''', (signal_type,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'oi_weight': row[0],
                'price_weight': row[1],
                'win_ratio': row[2],
                'total_predictions': row[3]
            }
        return None
    
    def calculate_win_ratio(self, days=30):
        """Calculate win ratio for the last N days"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                COUNT(*) as total,
                SUM(is_correct) as correct,
                signal_type
            FROM predictions
            WHERE is_correct IS NOT NULL
            AND date >= date('now', '-' || ? || ' days')
            GROUP BY signal_type
        '''
        
        df = pd.read_sql_query(query, conn, params=(days,))
        conn.close()
        
        if df.empty:
            return {}
        
        results = {}
        for _, row in df.iterrows():
            win_ratio = row['correct'] / row['total'] if row['total'] > 0 else 0
            results[row['signal_type']] = {
                'total': row['total'],
                'correct': row['correct'],
                'win_ratio': win_ratio * 100
            }
        
        return results
    
    def get_pending_predictions(self, date):
        """Get predictions that need to be verified (no next-day price yet)"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT symbol, actual_price FROM predictions
            WHERE date = ? AND actual_price_next_day IS NULL
        '''
        
        df = pd.read_sql_query(query, conn, params=(date,))
        conn.close()
        
        return df
    
    def get_performance_report(self):
        """Generate a comprehensive performance report"""
        conn = sqlite3.connect(self.db_path)
        
        # Overall stats
        overall_query = '''
            SELECT 
                COUNT(*) as total_predictions,
                SUM(is_correct) as correct_predictions,
                AVG(predicted_probability) as avg_probability,
                signal_type
            FROM predictions
            WHERE is_correct IS NOT NULL
            GROUP BY signal_type
        '''
        
        overall_df = pd.read_sql_query(overall_query, conn)
        
        # Recent performance (last 7 days)
        recent_query = '''
            SELECT 
                COUNT(*) as total,
                SUM(is_correct) as correct,
                signal_type
            FROM predictions
            WHERE is_correct IS NOT NULL
            AND date >= date('now', '-7 days')
            GROUP BY signal_type
        '''
        
        recent_df = pd.read_sql_query(recent_query, conn)
        
        # Current weights
        weights_query = '''
            SELECT signal_type, oi_weight, price_weight, win_ratio, total_predictions
            FROM model_weights
        '''
        
        weights_df = pd.read_sql_query(weights_query, conn)
        
        conn.close()
        
        return {
            'overall': overall_df,
            'recent': recent_df,
            'weights': weights_df
        }


# Test the tracker
if __name__ == "__main__":
    tracker = PredictionTracker()
    
    # Save a test prediction
    tracker.save_prediction(
        date="2026-04-25",
        symbol="TCS",
        signal_type="RISE_OI_SLIDE_PRICE",
        oi_change=123.55,
        price_change=-4.89,
        predicted_probability=100.0,
        actual_price=2401.00
    )
    
    print("Test prediction saved successfully")
    
    # Get performance report
    report = tracker.get_performance_report()
    print("\nPerformance Report:")
    print("Overall:", report['overall'])
    print("Weights:", report['weights'])
