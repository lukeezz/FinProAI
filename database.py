# database.py - FINAL VERSION
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib
import os

class NutritionDatabase:
    def __init__(self, db_path: str = "nutrition.db"):
        """Initialize SQLite database"""
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Create tables if they don't exist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            weight REAL DEFAULT 65.0,
            height REAL DEFAULT 170.0,
            age INTEGER DEFAULT 25,
            activity_level TEXT DEFAULT 'medium',
            goal TEXT DEFAULT 'maintain',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        ''')
        
        # Daily entries table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            food_name TEXT NOT NULL,
            portion TEXT DEFAULT 'Normal',
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            water_ml INTEGER DEFAULT 0,
            exercise_min INTEGER DEFAULT 0,
            nutrition_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Create indexes for performance
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_date 
        ON daily_entries(user_id, date)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_id 
        ON daily_entries(user_id)
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    # ===== USER MANAGEMENT =====
    def create_user(self, email: str, password: str, name: str) -> Optional[int]:
        """Create new user and return user_id"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            password_hash = self.hash_password(password)
            
            cursor.execute('''
            INSERT INTO users (email, password_hash, name)
            VALUES (?, ?, ?)
            ''', (email, password_hash, name))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            print(f"✅ User created: {email} (ID: {user_id})")
            return user_id
        except sqlite3.IntegrityError:
            print(f"❌ User already exists: {email}")
            return None
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return None
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            password_hash = self.hash_password(password)
            
            cursor.execute('''
            SELECT id, email, name, weight, height, age, activity_level, goal
            FROM users 
            WHERE email = ? AND password_hash = ?
            ''', (email, password_hash))
            
            user = cursor.fetchone()
            
            if user:
                # Update last login
                cursor.execute('''
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP
                WHERE id = ?
                ''', (user['id'],))
                conn.commit()
                
                user_dict = dict(user)
                conn.close()
                print(f"✅ User authenticated: {email}")
                return user_dict
            
            conn.close()
            print(f"❌ Authentication failed for: {email}")
            return None
        except Exception as e:
            print(f"❌ Error authenticating user: {e}")
            return None
    
    def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Get user profile by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, email, name, weight, height, age, activity_level, goal
            FROM users 
            WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            conn.close()
            
            return dict(user) if user else None
        except Exception as e:
            print(f"❌ Error getting user profile: {e}")
            return None
    
    def update_user_profile(self, user_id: int, **kwargs) -> bool:
        """Update user profile fields"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            allowed_fields = ['name', 'weight', 'height', 'age', 'activity_level', 'goal']
            updates = []
            values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)
            
            if not updates:
                return False
            
            values.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            
            success = cursor.rowcount > 0
            if success:
                print(f"✅ Profile updated for user ID: {user_id}")
            return success
        except Exception as e:
            print(f"❌ Error updating profile: {e}")
            return False
    
    def user_exists(self, email: str) -> bool:
        """Check if user with email exists"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT 1 FROM users WHERE email = ?', (email,))
            exists = cursor.fetchone() is not None
            conn.close()
            
            return exists
        except Exception as e:
            print(f"❌ Error checking user existence: {e}")
            return False
    
    # ===== DAILY ENTRIES MANAGEMENT =====
    def add_daily_entry(self, user_id: int, entry_data: Dict[str, Any]) -> bool:
        """Add a new daily entry for user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Extract data
            date = entry_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            food_name = entry_data.get('food', 'Unknown')
            
            # Handle both 'portion' and 'portion_grams'
            if 'portion' in entry_data:
                portion = entry_data.get('portion', 'Normal')
            elif 'portion_grams' in entry_data:
                portion = f"{entry_data.get('portion_grams')}g"
            else:
                portion = 'Normal'
            
            nutrition = entry_data.get('nutrition', {})
            calories = extract_number(nutrition.get('calories', '0 kcal'))
            protein = extract_number(nutrition.get('protein', '0 g'))
            fat = extract_number(nutrition.get('fat', '0 g'))
            carbs = extract_number(nutrition.get('carbs', '0 g'))
            
            water_ml = entry_data.get('water', 0)
            exercise_min = entry_data.get('exercise', 0)
            
            # Store nutrition data as JSON
            nutrition_json = json.dumps(nutrition)
            
            cursor.execute('''
            INSERT INTO daily_entries 
            (user_id, date, food_name, portion, calories, protein, fat, carbs, water_ml, exercise_min, nutrition_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, date, food_name, portion, calories, protein, fat, carbs, water_ml, exercise_min, nutrition_json))
            
            conn.commit()
            entry_id = cursor.lastrowid
            conn.close()
            
            print(f"✅ Entry added: {food_name} (ID: {entry_id}) for user {user_id}")
            return True
        except Exception as e:
            print(f"❌ Error adding daily entry: {e}")
            return False
    
    def get_daily_entries(self, user_id: int, date: Optional[str] = None) -> List[Dict]:
        """Get daily entries for user, optionally filtered by date"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if date:
                cursor.execute('''
                SELECT * FROM daily_entries 
                WHERE user_id = ? AND date = ?
                ORDER BY created_at DESC
                ''', (user_id, date))
            else:
                cursor.execute('''
                SELECT * FROM daily_entries 
                WHERE user_id = ?
                ORDER BY date DESC, created_at DESC
                ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            entries = []
            for row in rows:
                entry = dict(row)
                # Parse JSON nutrition data
                if entry.get('nutrition_data'):
                    entry['nutrition'] = json.loads(entry['nutrition_data'])
                else:
                    entry['nutrition'] = {
                        'calories': f"{entry.get('calories', 0)} kcal",
                        'protein': f"{entry.get('protein', 0)} g",
                        'fat': f"{entry.get('fat', 0)} g",
                        'carbs': f"{entry.get('carbs', 0)} g"
                    }
                entries.append(entry)
            
            print(f"✅ Retrieved {len(entries)} entries for user {user_id}")
            return entries
        except Exception as e:
            print(f"❌ Error getting daily entries: {e}")
            return []
    
    def get_daily_nutrition_summary(self, user_id: int, date: str) -> Dict:
        """Get daily nutrition summary for a specific date"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                COUNT(*) as food_count,
                SUM(calories) as total_calories,
                SUM(protein) as total_protein,
                SUM(fat) as total_fat,
                SUM(carbs) as total_carbs,
                SUM(water_ml) as total_water,
                SUM(exercise_min) as total_exercise
            FROM daily_entries 
            WHERE user_id = ? AND date = ?
            ''', (user_id, date))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                summary = dict(row)
                # Ensure all values are present
                default_values = {
                    'food_count': 0,
                    'total_calories': 0,
                    'total_protein': 0,
                    'total_fat': 0,
                    'total_carbs': 0,
                    'total_water': 0,
                    'total_exercise': 0
                }
                
                # Fill missing values with defaults
                for key, default in default_values.items():
                    if key not in summary or summary[key] is None:
                        summary[key] = default
                
                return summary
            else:
                return {
                    'food_count': 0,
                    'total_calories': 0,
                    'total_protein': 0,
                    'total_fat': 0,
                    'total_carbs': 0,
                    'total_water': 0,
                    'total_exercise': 0
                }
        except Exception as e:
            print(f"❌ Error getting daily summary: {e}")
            return {
                'food_count': 0,
                'total_calories': 0,
                'total_protein': 0,
                'total_fat': 0,
                'total_carbs': 0,
                'total_water': 0,
                'total_exercise': 0
            }
    
    def get_entries_by_date_range(self, user_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Get entries within a date range"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM daily_entries 
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date DESC, created_at DESC
            ''', (user_id, start_date, end_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            entries = []
            for row in rows:
                entry = dict(row)
                entries.append(entry)
            
            return entries
        except Exception as e:
            print(f"❌ Error getting entries by date range: {e}")
            return []
    
    def get_user_summary(self, user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Get summary statistics for user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = '''
            SELECT 
                date,
                COUNT(*) as entry_count,
                SUM(calories) as total_calories,
                SUM(protein) as total_protein,
                SUM(fat) as total_fat,
                SUM(carbs) as total_carbs,
                SUM(water_ml) as total_water,
                SUM(exercise_min) as total_exercise
            FROM daily_entries 
            WHERE user_id = ?
            '''
            
            params = [user_id]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " GROUP BY date ORDER BY date DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            summary = {
                'daily_summaries': [dict(row) for row in rows],
                'total_days': len(rows),
                'total_entries': sum(row['entry_count'] for row in rows) if rows else 0,
                'avg_calories': sum(row['total_calories'] for row in rows) / len(rows) if rows else 0,
                'avg_water': sum(row['total_water'] for row in rows) / len(rows) if rows else 0,
                'avg_exercise': sum(row['total_exercise'] for row in rows) / len(rows) if rows else 0
            }
            
            return summary
        except Exception as e:
            print(f"❌ Error getting user summary: {e}")
            return {}
    
    def delete_entry(self, user_id: int, entry_id: int) -> bool:
        """Delete a specific entry"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            DELETE FROM daily_entries 
            WHERE id = ? AND user_id = ?
            ''', (entry_id, user_id))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                print(f"✅ Entry {entry_id} deleted for user {user_id}")
            else:
                print(f"❌ Entry {entry_id} not found for user {user_id}")
            
            return deleted
        except Exception as e:
            print(f"❌ Error deleting entry: {e}")
            return False
    
    def get_all_users(self) -> List[Dict]:
        """Get all users (for admin purposes)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, email, name, created_at, last_login
            FROM users 
            ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Error getting users: {e}")
            return []
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Get table counts
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM daily_entries")
            stats['total_entries'] = cursor.fetchone()[0]
            
            # Get earliest and latest dates
            cursor.execute("SELECT MIN(date), MAX(date) FROM daily_entries")
            date_range = cursor.fetchone()
            stats['date_range'] = f"{date_range[0]} to {date_range[1]}" if date_range[0] and date_range[1] else "No data"
            
            # Get database file size
            if os.path.exists(self.db_path):
                stats['file_size_kb'] = os.path.getsize(self.db_path) / 1024
            
            conn.close()
            return stats
        except Exception as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
    
    def clear_user_data(self, user_id: int) -> bool:
        """Clear all data for a specific user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM daily_entries WHERE user_id = ?', (user_id,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            print(f"✅ Cleared {deleted_count} entries for user {user_id}")
            return True
        except Exception as e:
            print(f"❌ Error clearing user data: {e}")
            return False

# Helper function
def extract_number(val) -> float:
    """Extract number from string like '250 kcal'"""
    if isinstance(val, (int, float)):
        return float(val)
    
    if isinstance(val, str):
        try:
            # Remove non-numeric characters except dot
            num_str = ''.join(c for c in val if c.isdigit() or c == '.')
            return float(num_str) if num_str else 0.0
        except:
            return 0.0
    
    return 0.0

# Create a test user for demo
def create_test_user():
    """Create a test user for demonstration"""
    db = NutritionDatabase()
    
    test_email = "demo@example.com"
    test_password = "demo123"
    test_name = "Demo User"
    
    if not db.user_exists(test_email):
        user_id = db.create_user(test_email, test_password, test_name)
        if user_id:
            print(f"✅ Test user created: {test_email} / {test_password}")
            
            # Add some sample entries
            today = datetime.now().strftime('%Y-%m-%d')
            sample_entries = [
                {
                    'food': 'Nasi Goreng',
                    'portion': 'Normal',
                    'nutrition': {'calories': '250 kcal', 'protein': '8 g', 'fat': '10 g', 'carbs': '30 g'},
                    'water': 500,
                    'exercise': 0,
                    'date': today
                },
                {
                    'food': 'Ayam Bakar',
                    'portion': 'Normal',
                    'nutrition': {'calories': '220 kcal', 'protein': '28 g', 'fat': '10 g', 'carbs': '3 g'},
                    'water': 300,
                    'exercise': 30,
                    'date': today
                }
            ]
            
            for entry in sample_entries:
                db.add_daily_entry(user_id, entry)
            
            print("✅ Sample entries added for test user")
        else:
            print("❌ Failed to create test user")
    else:
        print("ℹ️ Test user already exists")

# Run when imported
if __name__ == "__main__":
    print("Initializing database...")
    db = NutritionDatabase()
    create_test_user()
    stats = db.get_database_stats()
    print(f"Database Stats: {stats}")