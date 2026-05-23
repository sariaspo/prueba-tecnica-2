from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from database import get_db_connection
from datetime import datetime

app = FastAPI(
    title="API REST de Datos Ambientales - Prueba Técnica 2",
    description="Servicio backend para la unificación y consulta de series meteorológicas.",
    version="1.0.0"
)

class LecturaIngesta(BaseModel):
    estacion_id: int
    timestamp: str
    precipitacion: float
    temperatura: float

class LecturaUpdate(BaseModel):
    precipitacion: float
    temperatura: float

@app.get("/api/v1/ambient/live", tags=["Consultas"])
def obtener_ultimo_registro():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT l.estacion_id, e.nombre as estacion_nombre, l.timestamp, l.precipitacion, l.temperatura 
        FROM lecturas l
        JOIN estaciones e ON l.estacion_id = e.id
        ORDER BY l.timestamp DESC 
        LIMIT 1
    """
    row = cursor.execute(query).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No hay registros en la base de datos.")
    return dict(row)

@app.post("/api/v1/ambient", status_code=201, tags=["Ingesta"])
def insertar_lectura(payload: LecturaIngesta):
    try:
        # Forzar validación de formato de fecha estándar
        datetime.strptime(payload.timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(status_code=400, detail="El formato de timestamp debe ser estricto: 'YYYY-MM-DD HH:MM:SS'")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lecturas (estacion_id, timestamp, precipitacion, temperatura)
        VALUES (?, ?, ?, ?)
    """, (payload.estacion_id, payload.timestamp, payload.precipitacion, payload.temperatura))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Lectura ambiental registrada con éxito."}

@app.get("/api/v1/ambient/historical", tags=["Consultas"])
def obtener_historico(
    start_date: str = Query(..., description="Fecha inicial en formato (YYYY-MM-DD HH:MM:SS)"),
    end_date: str = Query(..., description="Fecha final en formato (YYYY-MM-DD HH:MM:SS)")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM lecturas WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
    rows = cursor.execute(query, (start_date, end_date)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/v1/ambient/reports", tags=["Reportes"])
def generar_reporte_mensual(year: int = Query(...), month: int = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    filtro_mes = f"{year}-{month:02d}-%"
    query = """
        SELECT SUBSTR(timestamp, 1, 10) as dia, 
               ROUND(SUM(precipitacion), 4) as precipitacion_total,
               MAX(temperatura) as temp_max, 
               MIN(temperatura) as temp_min
        FROM lecturas 
        WHERE timestamp LIKE ? 
        GROUP BY dia 
        ORDER BY dia ASC
    """
    rows = cursor.execute(query, (filtro_mes,)).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Sin datos disponibles para el mes y año seleccionados.")
    return [dict(r) for r in rows]

@app.put("/api/v1/ambient/correction", tags=["Correcciones"])
def corregir_registro(timestamp: str = Query(...), estacion_id: int = Query(...), payload: LecturaUpdate = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existe = cursor.execute("SELECT 1 FROM lecturas WHERE timestamp = ? AND estacion_id = ?", (timestamp, estacion_id)).fetchone()
    if not existe:
        conn.close()
        raise HTTPException(status_code=404, detail="El registro que intenta corregir no existe.")
        
    cursor.execute("""
        UPDATE lecturas 
        SET precipitacion = ?, temperatura = ? 
        WHERE timestamp = ? AND estacion_id = ?
    """, (payload.precipitacion, payload.temperatura, timestamp, estacion_id))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Registro corregido correctamente en la base de datos."}