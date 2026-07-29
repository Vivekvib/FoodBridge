# migrate_db.py
from app import execute_query

def run_migration():
    print("🚀 Starting database schema migration...")

    # 1. In SQLite, we must add columns ONE AT A TIME without "IF NOT EXISTS"
    columns_to_add = [
        ("category", "VARCHAR(50) DEFAULT 'Cooked Veg'"),
        ("unit", "VARCHAR(30) DEFAULT 'Servings'"),
        ("packaging_note", "VARCHAR(100) DEFAULT 'Not specified'"),
        ("address", "TEXT DEFAULT 'Address not provided'"),
        ("latitude", "REAL NULL"),
        ("longitude", "REAL NULL")
    ]

    for col_name, col_def in columns_to_add:
        query = f"ALTER TABLE donations ADD COLUMN {col_name} {col_def};"
        try:
            execute_query(query, commit=True)
            print(f"✅ Added column: {col_name}")
        except Exception as e:
            # If the column already exists, SQLite throws an error which we can safely ignore
            error_msg = str(e).lower()
            if "duplicate column name" in error_msg or "already exists" in error_msg:
                print(f"ℹ️ Column '{col_name}' already exists, skipping.")
            else:
                print(f"⚠️ Could not add '{col_name}': {e}")

    # 2. Clean up existing 'quantity' values (convert strings like '5 kg' -> integer 5)
    try:
        print("\nCleaning up existing quantity values...")
        rows = execute_query("SELECT id, quantity FROM donations", fetch=True)
        
        if rows:
            for row in rows:
                # Handle both dict-like rows and tuple rows
                donation_id = row['id'] if isinstance(row, dict) else row[0]
                raw_qty = str(row['quantity'] if isinstance(row, dict) else row[1])
                
                # Extract only digits from strings like '5 kg' or '20 meals'
                digits_only = ''.join(filter(str.isdigit, raw_qty))
                clean_qty = int(digits_only) if digits_only else 0
                
                execute_query(
                    "UPDATE donations SET quantity = ? WHERE id = ?",
                    (clean_qty, donation_id),
                    commit=True
                )
            print("✅ Converted all existing quantity values to clean integers.")
        else:
            print("ℹ️ No existing donations found to update.")
            
    except Exception as e:
        print(f"⚠️ Error cleaning quantity values: {e}")

    print("\n🎉 Migration completed successfully! Your table is ready.")

if __name__ == "__main__":
    run_migration()