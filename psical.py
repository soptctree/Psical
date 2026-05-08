import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, time
import time as t_sleep

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Psical - Gestión Clínica", layout="wide")

def conectar_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="", database="psical_db"
    )

def obtener_pacientes():
    conn = conectar_db()
    df = pd.read_sql("SELECT id_paciente, nombre, IFNULL(cedula, 'S/N') as cedula FROM pacientes", conn)
    conn.close()
    return df

def verificar_disponibilidad(fecha, h_inicio, h_fin):
    conn = conectar_db()
    query = f"""
    SELECT * FROM citas WHERE fecha = '{fecha}' AND estado != 'Cancelada'
    AND (('{h_inicio}' >= hora_inicio AND '{h_inicio}' < hora_fin) OR
         ('{h_fin}' > hora_inicio AND '{h_fin}' <= hora_fin) OR
         (hora_inicio >= '{h_inicio}' AND hora_inicio < '{h_fin}'))
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df.empty

# --- NAVEGACIÓN ---
st.title("🧠 Psical: Gestión de Citas")
menu = st.sidebar.radio("Navegación", ["Agenda Diaria", "Agendar Cita", "Pacientes y Expedientes"])

# --- MÓDULO 1: AGENDA DIARIA ---
if menu == "Agenda Diaria":
    st.subheader("📋 Control Operativo del Día")
    fecha_agenda = st.date_input("Ver día:", value=datetime.now())
    
    conn = conectar_db()
    query = f"""
        SELECT c.id_cita, c.hora_inicio, c.hora_fin, p.nombre, IFNULL(p.cedula, 'S/N') as cedula, c.estado 
        FROM citas c JOIN pacientes p ON c.id_paciente = p.id_paciente 
        WHERE c.fecha = '{fecha_agenda}' ORDER BY c.hora_inicio ASC
    """
    try:
        df_todas = pd.read_sql(query, conn)
        df_activas = df_todas[df_todas['estado'] != 'Cancelada']
        
        # --- 1. MAPA DE DISPONIBILIDAD (Semáforo) ---
        st.write("### 🕒 Mapa de Disponibilidad")
        horas_dia = pd.date_range(start="07:00", end="17:00", freq="30min").time
        cols = st.columns(10)
        
        for i, h in enumerate(horas_dia):
            ocupado = False
            if not df_activas.empty:
                for _, r in df_activas.iterrows():
                    inicio = (datetime.min + r['hora_inicio']).time()
                    fin = (datetime.min + r['hora_fin']).time()
                    if h >= inicio and h < fin:
                        ocupado = True
                        break
            with cols[i % 10]:
                if ocupado: st.error(f"{h.strftime('%H:%M')}")
                else: st.success(f"{h.strftime('%H:%M')}")

        st.divider()

        # --- 2. RANGOS OCUPADOS ---
        if not df_activas.empty:
            st.write("### ⏳ Horarios Reservados")
            for _, row in df_activas.iterrows():
                h_i = (datetime.min + row['hora_inicio']).time().strftime('%H:%M')
                h_f = (datetime.min + row['hora_fin']).time().strftime('%H:%M')
                st.warning(f"**Ocupado de {h_i} a {h_f}** | Paciente: {row['nombre']} (ID: {row['cedula']})")
        else:
            st.info("🎉 Todo el día está libre. No hay rangos ocupados.")

        st.divider()

        # --- 3. GESTIÓN DE CITAS ---
        st.write("### 📑 Detalle y Asistencia")
        if df_todas.empty:
            st.info("No hay citas registradas para esta fecha.")
        else:
            for index, row in df_todas.iterrows():
                h_i = (datetime.min + row['hora_inicio']).time().strftime('%H:%M')
                h_f = (datetime.min + row['hora_fin']).time().strftime('%H:%M')
                
                with st.expander(f"⏰ {h_i} - {h_f} | 👤 {row['nombre']} ({row['estado']})"):
                    c1, c2 = st.columns(2)
                    with c1: st.write(f"Paciente ID: **{row['cedula']}**")
                    with c2:
                        nuevo_estado = st.selectbox("Actualizar:", ["Pendiente", "Asistió", "Ausente", "Cancelada"], 
                                                  index=["Pendiente", "Asistió", "Ausente", "Cancelada"].index(row['estado']), key=f"st_{row['id_cita']}")
                        if st.button("Guardar", key=f"b_{row['id_cita']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE citas SET estado = %s WHERE id_cita = %s", (nuevo_estado, row['id_cita']))
                            conn.commit()
                            st.rerun()
    except Exception as e: st.error(f"Error: {e}")
    finally: conn.close()

# --- MÓDULO 2: AGENDAR CITA ---
elif menu == "Agendar Cita":
    st.subheader("📅 Programar Sesión")
    df_p = obtener_pacientes()
    if df_p.empty: st.warning("Crea un paciente en la sección correspondiente.")
    else:
        with st.form("form_agendar", clear_on_submit=True):
            p_id = st.selectbox("Paciente", options=df_p['id_paciente'].tolist(),
                              format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]} ({df_p[df_p['id_paciente']==x]['cedula'].values[0]})")
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha")
            h_i = c2.time_input("Inicio", value=time(7,0))
            h_f = c3.time_input("Fin", value=time(7,30))
            
            if st.form_submit_button("Confirmar Cita"):
                if h_i >= h_f: st.error("La hora de fin debe ser posterior.")
                elif verificar_disponibilidad(fecha, h_i, h_f):
                    conn = conectar_db(); cursor = conn.cursor()
                    cursor.execute("INSERT INTO citas (id_paciente, fecha, hora_inicio, hora_fin) VALUES (%s,%s,%s,%s)", (p_id, fecha, h_i, h_f))
                    conn.commit(); conn.close()
                    st.success("✅ ¡Cita guardada!"); st.balloons()
                    t_sleep.sleep(1.5); st.rerun()
                else: st.error("❌ Conflicto de horario. Revisa la Agenda.")

# --- MÓDULO 3: PACIENTES Y EXPEDIENTES (UNIFICADO) ---
elif menu == "Pacientes y Expedientes":
    st.subheader("🏥 Expediente Clínico Profesional")
    tab1, tab2, tab3 = st.tabs(["Registrar Paciente", "Historial Médico", "Nueva Consulta"])

    with tab1:
        with st.form("reg_p"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre Completo")
            id_c = c2.text_input("Cédula")
            t = c1.text_input("Teléfono")
            m = c2.text_input("Correo")
            r = st.text_area("Antecedentes / Referencia")
            if st.form_submit_button("Guardar"):
                conn = conectar_db(); cursor = conn.cursor()
                cursor.execute("INSERT INTO pacientes (nombre, cedula, telefono, correo, referencia) VALUES (%s,%s,%s,%s,%s)", 
                             (n, id_c if id_c else None, t, m, r))
                conn.commit(); conn.close(); st.success("Registrado correctamente.")

    with tab2:
        df_p = obtener_pacientes()
        if not df_p.empty:
            sel_p = st.selectbox("Seleccionar Paciente:", options=df_p['id_paciente'].tolist(),
                               format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}")
            
            conn = conectar_db()
            query_h = f"SELECT * FROM historiales WHERE id_paciente = {sel_p} ORDER BY fecha DESC"
            df_hist = pd.read_sql(query_h, conn)
            
            if df_hist.empty:
                st.info("No hay historial clínico registrado aún.")
            else:
                for _, row in df_hist.iterrows():
                    with st.expander(f"🩺 Consulta: {row['fecha']}"):
                        v1, v2, v3, v4 = st.columns(4)
                        v1.metric("Peso", f"{row['peso']} kg")
                        v2.metric("Presión", row['presion_arterial'])
                        v3.metric("Temp.", f"{row['temperatura']}°C")
                        v4.metric("Altura", f"{row['altura']} m")
                        st.write(f"**Síntomas:** {row['sintomas']}")
                        st.write(f"**Diagnóstico:** {row['diagnostico']}")
                        st.success(f"**Receta/Recomendaciones:** {row['recomendaciones']}")
            conn.close()

    with tab3:
        st.write("### 📝 Nueva Evaluación Médica")
        df_p = obtener_pacientes()
        p_id = st.selectbox("Paciente:", options=df_p['id_paciente'].tolist(),
                          format_func=lambda x: f"{df_p[df_p['id_paciente']==x]['nombre'].values[0]}", key="cons_doc")
        
        conn = conectar_db()
        c_libres = pd.read_sql(f"SELECT id_cita, fecha FROM citas WHERE id_paciente={p_id} AND estado='Asistió' AND id_cita NOT IN (SELECT id_cita FROM historiales)", conn)
        
        if c_libres.empty:
            st.warning("No hay citas pendientes de informe. Asegúrate de marcar 'Asistió' en la Agenda.")
        else:
            with st.form("f_medico"):
                cita_sel = st.selectbox("Cita del día:", options=c_libres['id_cita'].tolist(),
                                      format_func=lambda x: f"Fecha: {c_libres[c_libres['id_cita']==x]['fecha'].values[0]}")
                c1, c2, c3, c4 = st.columns(4)
                peso = c1.number_input("Peso (kg)", step=0.1)
                presion = c2.text_input("Presión (ej: 120/80)")
                temp = c3.number_input("Temperatura (°C)", value=36.5, step=0.1)
                alt = c4.number_input("Altura (m)", step=0.01)
                sin = st.text_area("Síntomas")
                dia = st.text_area("Diagnóstico")
                rec = st.text_area("Tratamiento / Receta")
                
                if st.form_submit_button("Guardar Consulta"):
                    cursor = conn.cursor()
                    cursor.execute("""INSERT INTO historiales (id_paciente, id_cita, fecha, peso, altura, presion_arterial, temperatura, sintomas, diagnostico, recomendaciones) 
                                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                                   (p_id, cita_sel, str(c_libres[c_libres['id_cita']==cita_sel]['fecha'].values[0]), peso, alt, presion, temp, sin, dia, rec))
                    conn.commit(); conn.close()
                    st.success("✅ Consulta guardada exitosamente.")
                    t_sleep.sleep(1.5)
                    st.rerun()