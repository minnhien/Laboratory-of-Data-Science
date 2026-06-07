import pyodbc
import csv
import os
import sys
from datetime import datetime
# 1. CONFIGURATION
connection_string = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=tcp:131.114.50.57;'
    'DATABASE=Group_ID_2_DB;'
    'UID=Group_ID_2;'
    'PWD=AXMHLVML'
)

OUTPUT_DIR = 'data_splitting_v2' 

# 2. FUNCTIONS
def execute_sql(cursor, sql, description):
    try:
        cursor.execute(sql)
    except Exception as e:
        print(f"Warning ({description}): {e}")

def nuke_database(conn):
    """
    Cleaning Process: 
    Disable Foreign Keys -> Delete Data -> Reset ID Counters -> Enable Foreign Keys.
    """
    cursor = conn.cursor()
    print("\nSTARTING CLEANING PROCESS")

    # Disable Foreign Key constraints
    print("... Disabling all Foreign Key constraints")
    execute_sql(cursor, "EXEC sp_msforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT all'", "Disabled Constraints")

    #List of tables to clean)
    tables = [
        "song_artist",          
        "Published_song_fact", 
        "lyrics",               
        "category",             
        "album",                
        "date",                 
        "artist",               
        "artist_geography"      
    ]

    for table in tables:
        # Delete data
        execute_sql(cursor, f"DELETE FROM {table}", f"Deleted data from {table}")
        
        # RESET IDENTITY TO 0 
        # Skip 'date' table
        if table != "date":
            try:
                cursor.execute(f"SELECT OBJECTPROPERTY(OBJECT_ID('{table}'), 'TableHasIdentity')")
                result = cursor.fetchone()
                has_identity = result[0] if result else 0
                
                if has_identity:
                    cursor.execute(f"DBCC CHECKIDENT ('{table}', RESEED, 0)")
                    print(f"   -> Reseeded {table} to 0 (Next ID will be 1)")
            except Exception as e:
                print(f"   -> Info: Skipped reseed for {table} (Reason: {e})")

    # Re-enable Foreign Key constraints
    print("... Re-enabling all Foreign Key constraints")
    execute_sql(cursor, "EXEC sp_msforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT all'", "Enabled Constraints")
    
    conn.commit()
    print("\n CLEANING COMPLETE \n")

def clean_value(value, is_date=False):
    """
    Data Cleaning Function:
    - Converts empty strings/NULL strings to Python None (SQL NULL).
    - If is_date=True, attempts to parse and format the date to YYYY-MM-DD.
    """
    if value is None or value.strip() == '' or value.strip().lower() == 'null':
        return None
    
    if is_date:
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y']
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    return value

def load_csv_to_sql(file_path, table_name, connection_string, skip_identity_col=False, force_identity_insert=False, date_cols_indices=[]):
    print(f"--- [START] Loading table: {table_name} ---")
    
    if not os.path.exists(file_path):
        print(f" Error: File not found {file_path}")
        return

    conn = None
    cursor = None
    
    try:
        conn = pyodbc.connect(connection_string)
        conn.autocommit = False 
        cursor = conn.cursor()

        with open(file_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            try:
                headers = next(reader)
            except StopIteration:
                print(f"⚠️ Warning: File {table_name} is empty.")
                return

            # HEADER PROCESSING
            if skip_identity_col:
                final_headers = headers[1:]
                process_rows = lambda r: r[1:]
                adjusted_date_indices = [i-1 for i in date_cols_indices if i > 0]
            else:
                final_headers = headers
                process_rows = lambda r: r
                adjusted_date_indices = date_cols_indices

            columns_str = ', '.join([f"[{h}]" for h in final_headers])
            placeholders = ', '.join(['?'] * len(final_headers))
            insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            # HANDLE IDENTITY INSERT
            if force_identity_insert:
                try:
                    cursor.execute(f"SET IDENTITY_INSERT {table_name} ON")
                except Exception:
                    pass

            batch_size = 5000 
            rows_batch = []
            
            for row in reader:
                row_data = process_rows(row)
                cleaned_row = []
                for idx, val in enumerate(row_data):
                    is_date_col = idx in adjusted_date_indices
                    cleaned_row.append(clean_value(val, is_date=is_date_col))

                rows_batch.append(cleaned_row)
                
                # Batch Insert
                if len(rows_batch) == batch_size:
                    cursor.executemany(insert_query, rows_batch)
                    rows_batch = []

            # Insert remaining rows
            if rows_batch:
                cursor.executemany(insert_query, rows_batch)
            
            # Turn off IDENTITY_INSERT
            if force_identity_insert:
                try:
                    cursor.execute(f"SET IDENTITY_INSERT {table_name} OFF")
                except Exception:
                    pass

            conn.commit()
            print(f"✅ SUCCESS: Loaded data into {table_name}.")

    except Exception as e:
        if conn: conn.rollback()
        print(f"❌ CRITICAL ERROR in table {table_name}: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 3. MASTER EXECUTION FLOW

def main():
    #CLEANING DATABASE 
    try:
        conn = pyodbc.connect(connection_string)
        nuke_database(conn)
        conn.close()
    except Exception as e:
        print(f"Fatal Error connecting to DB: {e}")
        return

    #LOADING DATA FROM CSV
    print("\n=== STEP 2: LOADING DATA FROM CSV ===")

    # 1. Geography
    load_csv_to_sql(f"{OUTPUT_DIR}/artist_geography.csv", "artist_geography", connection_string, 
                    skip_identity_col=True, force_identity_insert=False)
    # 2. Artist
    load_csv_to_sql(f"{OUTPUT_DIR}/artist.csv", "artist", connection_string, 
                    skip_identity_col=True, force_identity_insert=False,
                    date_cols_indices=[7, 8, 9]) 
    # 3. Album
    load_csv_to_sql(f"{OUTPUT_DIR}/album.csv", "album", connection_string, 
                    skip_identity_col=True, force_identity_insert=False)   
    # 4. Date 
    load_csv_to_sql(f"{OUTPUT_DIR}/date.csv", "date", connection_string, 
                    skip_identity_col=False, force_identity_insert=False) 
    # 5. Category
    load_csv_to_sql(f"{OUTPUT_DIR}/category.csv", "category", connection_string, 
                    skip_identity_col=True, force_identity_insert=False)
    # 6. Lyrics
    load_csv_to_sql(f"{OUTPUT_DIR}/lyrics.csv", "lyrics", connection_string, 
                    skip_identity_col=False)

    # 7. Fact Table
    load_csv_to_sql(f"{OUTPUT_DIR}/Published_song_fact.csv", "Published_song_fact", connection_string, 
                    skip_identity_col=True, force_identity_insert=False) 
    # 8. Bridge Table
    load_csv_to_sql(f"{OUTPUT_DIR}/song_artist.csv", "song_artist", connection_string, 
                    skip_identity_col=False, force_identity_insert=False)

    print("\n>>> ALL TASKS COMPLETED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    main()