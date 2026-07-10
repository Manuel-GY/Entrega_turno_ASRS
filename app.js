// ---- ESTADO ----
let datosCargados = [];

// ---- INIT ----
document.addEventListener("DOMContentLoaded", () => {
    const hoy = new Date();
    const h = hoy.getHours();

    let fechaSugerida = hoy;
    const sel = document.getElementById("turnoInput");

    if (h >= 6 && h < 14) {
        sel.value = "T1_8H";
    } else if (h >= 14 && h < 22) {
        sel.value = "T2_8H";
    } else {
        sel.value = "T3_8H";
        if (h >= 22) fechaSugerida.setDate(hoy.getDate() + 1);
    }

    const dia = String(fechaSugerida.getDate()).padStart(2, "0");
    const mes = String(fechaSugerida.getMonth() + 1).padStart(2, "0");
    const anio = fechaSugerida.getFullYear();

    flatpickr("#fechaInput", {
        dateFormat: "d/m/Y",
        defaultDate: `${dia}/${mes}/${anio}`,
        disableMobile: "true",
    });

    const tema = localStorage.getItem("tema_tabla") || "light";
    document.body.setAttribute("data-theme", tema);

    cargarHistorial();
});

// ---- TEMA ----
function toggleTheme() {
    const body = document.body;
    const nuevo = body.getAttribute("data-theme") === "light" ? "dark" : "light";
    body.setAttribute("data-theme", nuevo);
    localStorage.setItem("tema_tabla", nuevo);
}

// ---- FECHAS ----
function toISODate(fStr) {
    if (!fStr) return "";
    const p = fStr.split("/");
    return p.length === 3 ? `${p[2]}-${p[1]}-${p[0]}` : fStr;
}

function formatearFecha(fechaStr) {
    if (!fechaStr) return "";
    const p = fechaStr.split("-");
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : fechaStr;
}

function labelTurno(t) {
    const m = {
        T1_8H: "Dia", T2_8H: "Tarde", T3_8H: "Noche",
        T_DIA_12H: "Dia 12h", T_NOCHE_12H: "Noche 12h",
    };
    return m[t] || t;
}

// ---- HELPERS ----
function escapeHTML(str) {
    if (!str) return "";
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" };
    return str.toString().replace(/[&<>'"]/g, (ch) => map[ch] || ch);
}

function setLoading(on) {
    document.getElementById("loading").style.display = on ? "block" : "none";
    document.getElementById("btnBuscar").disabled = on;
}

function toast(msg, error = false) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = error ? "error" : "";
    el.style.display = "block";
    setTimeout(() => (el.style.display = "none"), 3500);
}

function validarFecha() {
    const v = document.getElementById("fechaInput").value;
    if (!v) { toast("Selecciona una fecha", true); return null; }
    if (!/^\d{2}\/\d{2}\/\d{4}$/.test(v)) { toast("Usa el formato DD/MM/AAAA", true); return null; }
    return v;
}

// ---- CONSULTAR API ----
async function consultarDatos() {
    const fechaLocal = validarFecha();
    if (!fechaLocal) return;

    const fecha = toISODate(fechaLocal);
    const turno = document.getElementById("turnoInput").value;

    setLoading(true);
    try {
        const res = await fetch("/api/consultar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fecha, turno }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        renderizar(data, fecha, turno);
        toast("Datos actualizados y guardados ✔");
        cargarHistorial();
    } catch (e) {
        toast("Error: " + e.message, true);
    } finally {
        setLoading(false);
    }
}

// ---- GUARDAR COMENTARIOS ----
async function guardarComentarios() {
    const fechaLocal = validarFecha();
    if (!fechaLocal) return;

    const fecha = toISODate(fechaLocal);
    const turno = document.getElementById("turnoInput").value;

    const filas = [];
    document.querySelectorAll("#tablaTbody tr").forEach((tr) => {
        filas.push({
            hora_inicio: tr.dataset.hi,
            comentario: tr.querySelector(".inp-com")?.value || "",
            cod_sap: tr.querySelector(".inp-sap")?.value || "",
            tiempo_detencion: tr.querySelector(".inp-det")?.value || "",
        });
    });

    const com_gen = document.getElementById("comentarioGeneral").value;

    setLoading(true);
    try {
        const res = await fetch("/api/guardar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fecha, turno, filas, comentario_general: com_gen }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        toast(`Guardado: ${data.guardados} filas + Comentario General ✔`);
        cargarHistorial();
    } catch (e) {
        toast("Error al guardar: " + e.message, true);
    } finally {
        setLoading(false);
    }
}

// ---- CARGAR DESDE BD ----
async function cargarDesdeBD(fecha, turno) {
    setLoading(true);
    try {
        const res = await fetch(`/api/cargar?fecha=${encodeURIComponent(fecha)}&turno=${encodeURIComponent(turno)}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        if (data.tabla && data.tabla.length > 0) {
            renderizar({
                tabla: data.tabla,
                kpis: calcularKpis(data.tabla),
                comentario_general: data.comentario_general,
            }, fecha, turno, true);
            toast(`Cargados ${data.total} registros desde la BD`);
        } else {
            toast("No hay datos guardados para ese turno", true);
        }
    } catch (e) {
        toast("Error: " + e.message, true);
    } finally {
        setLoading(false);
    }
}

function calcularKpis(tabla) {
    const vals = tabla.filter((f) => f.inbound > 0 || f.outbound > 0);
    if (!vals.length) return { inbound: "0.0", outbound: "0.0" };
    const avgIn = (vals.reduce((a, f) => a + parseFloat(f.inbound || 0), 0) / vals.length).toFixed(1);
    const avgOut = (vals.reduce((a, f) => a + parseFloat(f.outbound || 0), 0) / vals.length).toFixed(1);
    return { inbound: avgIn, outbound: avgOut };
}

// ---- HISTORIAL ----
async function cargarHistorial() {
    try {
        const res = await fetch("/api/historial");
        const data = await res.json();
        const lista = document.getElementById("historialList");
        if (!data.length) {
            lista.innerHTML = '<div style="font-size:12px;color:var(--muted);text-align:center;padding:10px">Sin registros aun</div>';
            return;
        }
        lista.innerHTML = data.map((r) => `
            <div class="hist-item" onclick="cargarDesdeBD('${escapeHTML(r.fecha)}','${escapeHTML(r.turno)}')">
                <strong>${escapeHTML(formatearFecha(r.fecha))} &mdash; ${escapeHTML(labelTurno(r.turno))}</strong>
                ${parseInt(r.filas)} filas &middot; ${escapeHTML(r.ultima_vez.substring(0, 16))}
            </div>`).join("");
    } catch (_) { /* silencioso */ }
}

// ---- RENDERIZAR TABLA ----
function renderizar(data, fecha, turno, desdeBD = false) {
    document.getElementById("emptyState").style.display = "none";
    document.getElementById("gridMain").style.display = "grid";
    document.getElementById("extraComments").style.display = "block";
    document.getElementById("btnGuardar").style.display = "";
    document.getElementById("btnCapture").style.display = "";

    document.getElementById("comentarioGeneral").value = data.comentario_general || "";
    document.getElementById("badgeTurno").textContent = `${formatearFecha(fecha)} · ${labelTurno(turno)}`;
    document.getElementById("turnoInput").value = turno;

    const tbody = document.getElementById("tablaTbody");
    tbody.innerHTML = "";

    if (!data.tabla || data.tabla.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="color:var(--muted);text-align:center;padding:20px">Sin registros para este horario.</td></tr>';
        return;
    }

    data.tabla.forEach((fila, idx) => {
        const ib = parseFloat(fila.inbound || 0);
        const ob = parseFloat(fila.outbound || 0);
        const ibPct = Math.min((ib / 15) * 100, 100);
        const obPct = Math.min((ob / 10) * 100, 100);
        const ibCol = ib >= 11.0 ? "#10b981" : "#ef4444";
        const obCol = ob >= 7.5 ? "#10b981" : "#ef4444";
        const defCom = idx === 0 ? "TURNO ANTERIOR" : (fila.comentario || "");
        const defSap = fila.cod_sap || "";
        const defDet = fila.tiempo_detencion || "";

        const tr = document.createElement("tr");
        tr.dataset.hi = fila.hora_inicio || "";
        tr.innerHTML = `
            <td class="hora-texto">${escapeHTML(fila.hora_inicio)}</td>
            <td class="hora-texto">${escapeHTML(fila.hora_fin)}</td>
            <td class="meta-texto">11.0</td>
            <td style="position:relative;text-align:left;padding-left:12px">
                <div style="position:absolute;left:0;top:15%;height:70%;width:${ibPct}%;background:${ibCol};opacity:.15;border-radius:0 4px 4px 0;z-index:1"></div>
                <span style="position:relative;z-index:2;font-weight:800;color:${ibCol};font-size:14px">${ib > 0 ? ib.toFixed(1) : "0.0"}</span>
            </td>
            <td class="meta-texto">7.5</td>
            <td style="position:relative;text-align:left;padding-left:12px">
                <div style="position:absolute;left:0;top:15%;height:70%;width:${obPct}%;background:${obCol};opacity:.15;border-radius:0 4px 4px 0;z-index:1"></div>
                <span style="position:relative;z-index:2;font-weight:800;color:${obCol};font-size:14px">${ob > 0 ? ob.toFixed(1) : "0.0"}</span>
            </td>
            <td><input type="text" class="input-cell inp-com" value="${escapeHTML(defCom)}" autocomplete="off" style="text-align: left;"></td>
            <td><input type="text" class="input-cell inp-det" value="${escapeHTML(defDet)}" autocomplete="off" placeholder="\u2014" style="text-align: center; font-family: 'JetBrains Mono', monospace;"></td>
            <td><input type="text" class="input-cell inp-sap" value="${escapeHTML(defSap)}" autocomplete="off" style="text-align: center; font-family: 'JetBrains Mono', monospace; font-weight: bold;"></td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById("kpiIn").textContent = data.kpis?.inbound ?? "\u2014";
    document.getElementById("kpiOut").textContent = data.kpis?.outbound ?? "\u2014";
}

// ---- CAPTURA ----
function copiarImagen() {
    const btn = document.getElementById("btnCapture");
    if (!btn) return;

    if (typeof html2canvas === "undefined") {
        toast("Error: html2canvas no esta cargado.", true);
        return;
    }

    const zona = document.getElementById("zonaCaptura");
    if (!zona) {
        toast("Error: No se encontro #zonaCaptura.", true);
        return;
    }

    try {
        btn.textContent = "Procesando...";
        btn.disabled = true;
        const bgColor = getComputedStyle(document.body).getPropertyValue("--bg").trim() || "#f1f5f9";

        const ta = document.getElementById("comentarioGeneral");
        let printDiv = null;
        if (ta) {
            printDiv = document.createElement("div");
            printDiv.style.cssText = ta.style.cssText;
            printDiv.style.height = "100px";
            printDiv.style.border = "1px solid var(--border)";
            printDiv.style.borderRadius = "6px";
            printDiv.style.background = "var(--input-bg)";
            printDiv.style.color = "var(--text)";
            printDiv.style.padding = "12px";
            printDiv.style.fontFamily = "inherit";
            printDiv.style.fontSize = "14px";
            printDiv.style.whiteSpace = "pre-wrap";
            printDiv.style.wordBreak = "break-word";
            printDiv.innerHTML = escapeHTML(ta.value).replace(/\n/g, "<br>");
            ta.parentNode.insertBefore(printDiv, ta);
            ta.style.display = "none";
        }

        const sidebar = document.querySelector(".sidebar");
        if (sidebar) sidebar.style.display = "none";

        const originalWidth = zona.style.width;
        const originalMaxWidth = zona.style.maxWidth;
        zona.style.width = "1800px";
        zona.style.maxWidth = "1800px";

        const restaurarUI = () => {
            zona.style.width = originalWidth;
            zona.style.maxWidth = originalMaxWidth;
            if (sidebar) sidebar.style.display = "";
            if (printDiv) printDiv.remove();
            if (ta) ta.style.display = "block";
            btn.textContent = "\uD83D\uDCCB Copiar Reporte";
            btn.disabled = false;
        };

        const descargarRespaldo = (motivo) => {
            console.warn("Descarga de respaldo:", motivo);
            try {
                const a = document.createElement("a");
                a.download = "Reporte_Turno.png";
                a.href = canvas.toDataURL("image/png");
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                toast("Imagen descargada (Portapapeles no disponible en HTTP)");
            } catch (err) {
                console.error("Error generando dataURL:", err);
                toast("Error de seguridad al exportar la imagen.", true);
            } finally {
                restaurarUI();
            }
        };

        html2canvas(zona, {
            scale: 2.5,
            backgroundColor: bgColor,
            logging: false,
            useCORS: true,
            allowTaint: true,
        }).then((canvas) => {
            const isClipboardSupported =
                navigator.clipboard &&
                typeof navigator.clipboard.write === "function" &&
                typeof window.ClipboardItem !== "undefined";

            if (!isClipboardSupported) {
                descargarRespaldo("Navegador sin Clipboard API");
                return;
            }

            canvas.toBlob(async (blob) => {
                if (!blob) {
                    descargarRespaldo("No se pudo generar blob");
                    return;
                }
                try {
                    const item = new ClipboardItem({ "image/png": blob });
                    await navigator.clipboard.write([item]);
                    toast("Imagen copiada al portapapeles ✔");
                    restaurarUI();
                } catch (err) {
                    descargarRespaldo(err.message);
                }
            }, "image/png");
        }).catch((e) => {
            console.error("Error html2canvas:", e);
            toast("Error al capturar: " + e.message, true);
            restaurarUI();
        });
    } catch (err) {
        console.error("Error global copiarImagen:", err);
        toast("Error al iniciar la captura de pantalla.", true);
        btn.textContent = "\uD83D\uDCCB Copiar Reporte";
        btn.disabled = false;
    }
}
