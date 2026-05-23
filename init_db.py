import sqlite3
import pandas as pd
import os

DB_NAME = "ambiental.db"

def inicializar_base_de_datos():
    print("🚀 Iniciando procesamiento y unificación de datos ambientales...")
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(BASE_DIR, "data")

    try:
        df_datos = pd.read_csv(os.path.join(data_dir, "datos.csv"), encoding='utf-8-sig')
        df_estaciones_raw = pd.read_csv(os.path.join(data_dir, "estaciones.csv"), delimiter=';', encoding='utf-8-sig')
        df_fecha = pd.read_csv(os.path.join(data_dir, "fecha.csv"), delimiter=';', encoding='utf-8-sig')
        df_tiempo = pd.read_csv(os.path.join(data_dir, "tiempo.csv"), delimiter=';', encoding='utf-8-sig')
    except FileNotFoundError as e:
        print(f"❌ ERROR: No se encontraron los CSV en la carpeta 'data'. Detalle: {e}")
        return

    for df in [df_datos, df_estaciones_raw, df_fecha, df_tiempo]:
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")

    df_fecha['contador'] = df_fecha['contador'].astype(int)
    df_tiempo['contador'] = df_tiempo['contador'].astype(int)

    df_fecha['fecha_std'] = pd.to_datetime(df_fecha['fecha'], format='%d/%m/%Y', errors='coerce').dt.strftime('%Y-%m-%d')
    df_tiempo['tiempo_std'] = df_tiempo['tiempo'].astype(str).str.replace('"', '').str.strip()

    print("🔄 Unificando dimensiones de fecha y tiempo de 'estaciones.csv'...")
    df_estaciones_raw['fecha'] = df_estaciones_raw['fecha'].astype(int)
    df_estaciones_raw['tiempo'] = df_estaciones_raw['tiempo'].astype(int)
    
    m1 = pd.merge(df_estaciones_raw, df_fecha[['contador', 'fecha_std']], left_on='fecha', right_on='contador', how='inner')
    m1 = pd.merge(m1, df_tiempo[['contador', 'tiempo_std']], left_on='tiempo', right_on='contador', how='inner')
    m1['timestamp'] = m1['fecha_std'] + ' ' + m1['tiempo_std']
    m1 = m1.rename(columns={'estacion': 'estacion_id'})
    final_estaciones = m1[['estacion_id', 'timestamp', 'precipitacion', 'temperatura']].copy()

    print("🔄 Procesando marcas de tiempo de 'datos.csv'...")
    df_datos['fecha'] = df_datos['fecha'].astype(int)
    df_datos['tiempo'] = df_datos['tiempo'].astype(int)
    
    m2 = pd.merge(df_datos, df_fecha[['contador', 'fecha_std']], left_on='fecha', right_on='contador', how='inner')
    m2 = pd.merge(m2, df_tiempo[['contador', 'tiempo_std']], left_on='tiempo', right_on='contador', how='inner')
    m2['timestamp'] = m2['fecha_std'] + ' ' + m2['tiempo_std']
    m2 = m2.rename(columns={'estacion': 'estacion_id', 'lluvia': 'precipitacion'})
    final_datos = m2[['estacion_id', 'timestamp', 'precipitacion', 'temperatura']].copy()

    df_lecturas_total = pd.concat([final_estaciones, final_datos], ignore_index=True)
    df_lecturas_total = df_lecturas_total.dropna(subset=['timestamp'])
    df_lecturas_total = df_lecturas_total.drop_duplicates(subset=['estacion_id', 'timestamp'])

    estaciones_unicas = df_lecturas_total['estacion_id'].unique()
    df_catalogo_estaciones = pd.DataFrame({
        'id': [int(uid) for uid in estaciones_unicas],
        'nombre': [f"Estación Monitoreo {int(uid)}" for uid in estaciones_unicas]
    })

    db_path = os.path.join(BASE_DIR, DB_NAME)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS lecturas;")
    cursor.execute("DROP TABLE IF EXISTS estaciones;")

    cursor.execute("CREATE TABLE estaciones (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL);")
    cursor.execute("""
    CREATE TABLE lecturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estacion_id INTEGER,
        timestamp TEXT NOT NULL,
        precipitacion REAL,
        temperatura REAL,
        FOREIGN KEY (estacion_id) REFERENCES estaciones(id)
    );
    """)

    # Optimización mediante índices para consultas ultrarrápidas en la API
    cursor.execute("CREATE INDEX idx_lecturas_timestamp ON lecturas(timestamp);")
    cursor.execute("CREATE INDEX idx_lecturas_estacion_time ON lecturas(estacion_id, timestamp);")

    print("💾 Guardando en la base de datos SQL...")
    df_catalogo_estaciones.to_sql('estaciones', conn, if_exists='append', index=False)
    df_lecturas_total.to_sql('lecturas', conn, if_exists='append', index=False)

    conn.commit()
    conn.close()
    print(f"✅ ¡Base de datos '{DB_NAME}' creada con {len(df_lecturas_total)} registros!")

if __name__ == "__main__":
    inicializar_base_de_datos()