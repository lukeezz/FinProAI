# clear_database.py
import sqlite3
import os

def clear_database(db_path="nutrition.db"):
    """
    Membersihkan SEMUA data dari database SQLite.
    WARNING: Semua data akan dihapus permanen!
    """
    
    print("🧹 Cleaning database...")
    
    if not os.path.exists(db_path):
        print(f"❌ Database '{db_path}' not found!")
        return False
    
    try:
        # Koneksi ke database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Dapatkan semua nama tabel
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        # Hapus data dari semua tabel
        deleted_counts = {}
        for table in tables:
            table_name = table[0]
            if table_name != 'sqlite_sequence':
                # Hitung jumlah data sebelum dihapus
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_before = cursor.fetchone()[0]
                
                # Hapus semua data
                cursor.execute(f"DELETE FROM {table_name}")
                deleted_counts[table_name] = count_before
        
        # Reset auto-increment
        cursor.execute("DELETE FROM sqlite_sequence")
        
        # Commit perubahan
        conn.commit()
        conn.close()
        
        # Tampilkan hasil
        print("✅ Database cleared successfully!")
        print("\n📊 Deleted records:")
        for table, count in deleted_counts.items():
            print(f"  • {table}: {count} records")
        
        # Cek ukuran file setelah dibersihkan
        size_kb = os.path.getsize(db_path) / 1024
        print(f"\n📏 Database size: {size_kb:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

if __name__ == "__main__":
    clear_database()