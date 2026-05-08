import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, time, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Psical - Gestión Clínica", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
def conectar_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="", # Tu contraseña aquí
        database="psical_db"
    )

# --- FUNCIONES DE AUXILIO ---
def obtener_pacientes():
    conn = conectar_db()
    df = pd.read_sql("SELECT id_paciente, nombre FROM pacientes", conn)
    conn.close()
    return df

def verificar_disponibilidad(fecha, h_inicio, h_fin):
    conn = conectar_db()
    # Solo choca si la cita NO está cancelada
    query = f"""
    SELECT * FROM citas 
    WHERE fecha = '{fecha}' 
    AND estado != 'Cancelada'
    AND (
        ('{h_inicio}' >= hora_inicio AND '{h_inicio}' < hora_fin) OR
        ('{h_fin}' > hora_inicio AND '{h_fin}' <= hora_fin) OR
        (hora_inicio >= '{h_inicio}' AND hora_inicio < '{h_fin}')
    )
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df.empty

# --- INTERFAZ STREAMLIT ---
st.title("🧠 Psical: Gestión de Citas")

menu = st.sidebar.radio("Navegación", ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"])

# --- MÓDULO 1: AGENDA DIARIA ---
if menu == "Agenda Diaria":
    st.subheader("📋 Control Operativo del Día")
    fecha_agenda = st.date_input("Ver día:", value=datetime.now())
    
    conn = conectar_db()
    # Importante: Traemos todas para el detalle, pero filtraremos para lo visual
    query = f"""
        SELECT c.id_cita, c.hora_inicio, c.hora_fin, p.nombre, c.estado 
        FROM citas c 
        JOIN pacientes p ON c.id_paciente = p.id_paciente 
        WHERE c.fecha = '{fecha_agenda}' 
        ORDER BY c.hora_inicio ASC
    """
    
    try:
        df_todas = pd.read_sql(query, conn)
        # Filtramos las que ocupan espacio (las que no están canceladas)
        df_activas = df_todas[df_todas['estado'] != 'Cancelada']
        
        # --- PARRILLA DE DISPONIBILIDAD (Semáforo) ---
        st.write("### 🕒 Mapa de Disponibilidad")
        horas_dia = pd.date_range(start="07:00", end="17:00", freq="30min").time
        cols = st.columns(10)
        
        for i, h in enumerate(horas_dia):
            ocupado = False
            if not df_activas.empty:
                for _, cita in df_activas.iterrows():
                    inicio = (datetime.min + cita['hora_inicio']).time()
                    fin = (datetime.min + cita['hora_fin']).time()
                    if h >= inicio and h < fin:
                        ocupado = True
                        break
            
            with cols[i % 10]:
                if ocupado:
                    st.error(f"🔴 {h.strftime('%H:%M')}")
                else:
                    st.success(f"🟢 {h.strftime('%H:%M')}")

        st.divider()

        # --- MEJORA VISUAL: LÍNEA DE TIEMPO ---
        if not df_activas.empty:
            st.write("### ⏳ Rangos Ocupados Actualmente")
            for _, row in df_activas.iterrows():
                h_i = (datetime.min + row['hora_inicio']).time().strftime('%H:%M')
                h_f = (datetime.min + row['hora_fin']).time().strftime('%H:%M')
                st.warning(f"**Ocupado de {h_i} a {h_f}** | Paciente: {row['nombre']}")
        else:
            st.info("No hay rangos ocupados. Todo el día está libre.")

        st.divider()

        # --- DETALLE DE CITAS (Para cambiar estados) ---
        st.write("### 📑 Detalle y Gestión de Asistencia")
        if df_todas.empty:
            st.info("No hay registros para hoy.")
        else:
            for index, row in df_todas.iterrows():
                h_i_formato = (datetime.min + row['hora_inicio']).time().strftime('%H:%M')
                h_f_formato = (datetime.min + row['hora_fin']).time().strftime('%H:%M')
                
                # Color diferente si está cancelada
                titulo = f"⏰ {h_i_formato} - {h_f_formato} | 👤 {row['nombre']}"
                if row['estado'] == 'Cancelada':
                    titulo += " (CANCELADA - ESPACIO LIBRE)"

                with st.expander(titulo):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Estado actual:** :blue[{row['estado']}]")
                    with c2:
                        nuevo_estado = st.selectbox("Cambiar a:", 
                                                  ["Pendiente", "Asistió", "Ausente", "Cancelada"], 
                                                  index=["Pendiente", "Asistió", "Ausente", "Cancelada"].index(row['estado']),
                                                  key=f"estado_{row['id_cita']}")
                        if st.button("Actualizar Cita", key=f"btn_{row['id_cita']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE citas SET estado = %s WHERE id_cita = %s", (nuevo_estado, row['id_cita']))
                            conn.commit()
                            st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        conn.close()

# --- MÓDULO 2: AGENDAR CITA ---
elif menu == "Agendar Cita":
    st.subheader("📅 Programar Nueva Sesión")
    df_p = obtener_pacientes()
    
    if df_p.empty:
        st.warning("Registra un paciente primero.")
    else:
        # Usamos un contenedor para mensajes de error/éxito fuera del form
        mensaje_placeholder = st.empty()
        
        with st.form("form_nueva_cita", clear_on_submit=True):
            paciente_id = st.selectbox("Paciente", options=df_p['id_paciente'].tolist(),
                                     format_func=lambda x: df_p[df_p['id_paciente']==x]['nombre'].values[0])
            
            c_f, c_h1, c_h2 = st.columns(3)
            with c_f:
                fecha = st.date_input("Fecha", value=datetime.now())
            with c_h1:
                h_inicio = st.time_input("Hora Inicio", value=time(7,0))
            with c_h2:
                h_fin = st.time_input("Hora Fin", value=time(7,30))
            
            submit = st.form_submit_button("Confirmar Agenda")
            
            if submit:
                if h_inicio >= h_fin:
                    mensaje_placeholder.error("La hora de fin debe ser mayor a la de inicio.")
                elif verificar_disponibilidad(fecha, h_inicio, h_fin):
                    try:
                        conn = conectar_db()
                        cursor = conn.cursor()
                        query = "INSERT INTO citas (id_paciente, fecha, hora_inicio, hora_fin, estado) VALUES (%s, %s, %s, %s, 'Pendiente')"
                        cursor.execute(query, (paciente_id, fecha, h_inicio, h_fin))
                        conn.commit()
                        conn.close()
                        
                        # Mensaje visual de éxito
                        st.success(f"✅ ¡Cita guardada con éxito para las {h_inicio}!")
                        st.balloons() # Efecto visual opcional para confirmar éxito
                        
                        # Pequeña pausa para que el usuario vea el mensaje antes del rerun
                        import time as t_sleep
                        t_sleep.sleep(1.5)
                        st.rerun()
                        
                    except Exception as e:
                        mensaje_placeholder.error(f"Error al guardar: {e}")
                else:
                    mensaje_placeholder.error("❌ Horario ocupado. Por favor revisa la Agenda Diaria.")

# --- MÓDULO 3: PACIENTES ---
elif menu == "Pacientes y Expedientes":
    st.subheader("👤 Administración de Pacientes")
    tab_reg, tab_exp = st.tabs(["Registrar Nuevo", "Historial Clínico"])
    
    with tab_reg:
        with st.form("registro_p"):
            nombre = st.text_input("Nombre Completo")
            tel = st.text_input("Teléfono")
            cor = st.text_input("Correo")
            if st.form_submit_button("Guardar"):
                if nombre:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO pacientes (nombre, telefono, correo) VALUES (%s, %s, %s)", (nombre, tel, cor))
                    conn.commit()
                    conn.close()
                    st.success("Registrado.")

    with tab_exp:
        df_p = obtener_pacientes()
        if not df_p.empty:
            sel_p = st.selectbox("Expediente de:", options=df_p['id_paciente'].tolist(),
                               format_func=lambda x: df_p[df_p['id_paciente']==x]['nombre'].values[0])
            conn = conectar_db()
            historial = pd.read_sql(f"SELECT fecha, hora_inicio, estado FROM citas WHERE id_paciente = {sel_p} ORDER BY fecha DESC", conn)
            conn.close()
            st.dataframe(historial, use_container_width=True)