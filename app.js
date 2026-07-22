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

    document.querySelectorAll(".btn").forEach((btn) => {
        btn.addEventListener("click", function (e) {
            const ripple = document.createElement("span");
            ripple.classList.add("ripple");
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + "px";
            ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
            ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
            this.appendChild(ripple);
            ripple.addEventListener("animationend", () => ripple.remove());
        });
    });
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

function turnoColorClass(t) {
    if (t === "T1_8H" || t === "T_DIA_12H") return "turno-dia";
    if (t === "T2_8H") return "turno-tarde";
    return "turno-noche";
}

function horasTurno(t) {
    if (t === "T_DIA_12H" || t === "T_NOCHE_12H") return 12;
    return 8;
}

// ---- HELPERS ----
function escapeHTML(str) {
    if (!str) return "";
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" };
    return str.toString().replace(/[&<>'"]/g, (ch) => map[ch] || ch);
}

function animateKPI(elementId, targetValue) {
    const el = document.getElementById(elementId);
    const num = parseFloat(targetValue);
    if (isNaN(num)) {
        el.textContent = targetValue;
        return;
    }
    const duration = 600;
    const startTime = performance.now();
    const startVal = 0;
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = startVal + (num - startVal) * eased;
        el.textContent = current.toFixed(1);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

function setLoading(on) {
    document.getElementById("loading").style.display = on ? "block" : "none";
    document.getElementById("btnBuscar").disabled = on;
}

function toast(msg, error = false) {
    const el = document.getElementById("toast");
    const iconOk = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    const iconErr = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    el.innerHTML = (error ? iconErr : iconOk) + '<span>' + escapeHTML(msg) + '</span>';
    el.className = error ? "error" : "";
    el.style.display = "flex";
    el.classList.remove("toast-hide");
    clearTimeout(el._timer);
    el._timer = setTimeout(() => {
        el.classList.add("toast-hide");
        setTimeout(() => { el.style.display = "none"; }, 300);
    }, 3500);
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
        toast("Datos actualizados y guardados");
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
    document.querySelectorAll("#tablaOT tbody tr").forEach((tr) => {
        filas.push({
            hora_inicio: tr.dataset.hi,
            comentario: tr.querySelector(".inp-ot")?.value || "",
            obs: tr.querySelector(".inp-obs")?.value || "",
            cod_sap: "",
            tiempo_detencion: "",
        });
    });

    setLoading(true);
    try {
        const res = await fetch("/api/guardar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fecha, turno, filas, comentario_general: "" }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        toast(`Guardado: ${data.guardados} filas + Comentario General`);
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
    if (!vals.length) return { inbound: "0.0", outbound: "0.0", horas: 0, cumplimiento: "0" };
    const avgIn = (vals.reduce((a, f) => a + parseFloat(f.inbound || 0), 0) / vals.length).toFixed(1);
    const avgOut = (vals.reduce((a, f) => a + parseFloat(f.outbound || 0), 0) / vals.length).toFixed(1);
    const horasConDatos = vals.length;
    const cumple = vals.filter(f => parseFloat(f.inbound || 0) >= 11.0 && parseFloat(f.outbound || 0) >= 7.5).length;
    const pctCumple = horasConDatos > 0 ? ((cumple / horasConDatos) * 100).toFixed(0) : "0";
    return { inbound: avgIn, outbound: avgOut, horas: horasConDatos, cumplimiento: pctCumple };
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
            <div class="hist-item ${turnoColorClass(r.turno)}" onclick="cargarDesdeBD('${escapeHTML(r.fecha)}','${escapeHTML(r.turno)}')">
                <strong>${escapeHTML(formatearFecha(r.fecha))} &mdash; ${escapeHTML(labelTurno(r.turno))}</strong>
                ${parseInt(r.filas)} filas &middot; ${escapeHTML(r.ultima_vez.substring(0, 16))}
            </div>`).join("");
    } catch (_) { /* silencioso */ }
}

// ---- RENDERIZAR ----
function renderizar(data, fecha, turno, desdeBD = false) {
    document.getElementById("emptyState").style.display = "none";
    document.getElementById("reportContent").className = "active";
    document.getElementById("btnGuardar").style.display = "";
    document.getElementById("btnCapture").style.display = "";

    document.getElementById("badgeTurno").textContent = `${formatearFecha(fecha)} \u00B7 ${labelTurno(turno)}`;
    document.getElementById("reportDate").textContent = `${formatearFecha(fecha)} \u00B7 ${labelTurno(turno)}`;
    document.getElementById("turnoInput").value = turno;

    const tabla = data.tabla || [];
    // ---- TABLA PRINCIPAL ----
    const tbody = document.getElementById("tablaTbody");
    tbody.innerHTML = "";

    if (tabla.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center;padding:24px">Sin registros para este horario.</td></tr>';
    } else {
        tabla.forEach((fila, idx) => {
            const ib = parseFloat(fila.inbound || 0);
            const ob = parseFloat(fila.outbound || 0);
            const ibPct = Math.min((ib / 15) * 100, 100);
            const obPct = Math.min((ob / 10) * 100, 100);
            const ibOk = ib >= 11.0;
            const obOk = ob >= 7.5;
            const ibCls = ibOk ? "ok" : "fail";
            const obCls = obOk ? "ok" : "fail";

            let rowCls = "";
            if (ibOk && obOk) rowCls = "row-ok";
            else if (ibOk || obOk) rowCls = "row-warn";
            else if (ib > 0 || ob > 0) rowCls = "row-fail";

            const tr = document.createElement("tr");
            tr.className = rowCls;
            tr.innerHTML = `
                <td class="hora-cell">${escapeHTML(fila.hora_inicio)}</td>
                <td class="hora-cell">${escapeHTML(fila.hora_fin)}</td>
                <td class="bar-cell">
                    <div class="bar-track"><div class="bar-fill ${ibCls}" style="width:${ibPct}%"></div></div>
                    <div>
                        <span class="bar-val ${ibCls}">${ib > 0 ? ib.toFixed(1) : "0.0"}</span>
                        <div class="bar-meta">meta 11.0</div>
                    </div>
                </td>
                <td class="bar-cell">
                    <div class="bar-track"><div class="bar-fill ${obCls}" style="width:${obPct}%"></div></div>
                    <div>
                        <span class="bar-val ${obCls}">${ob > 0 ? ob.toFixed(1) : "0.0"}</span>
                        <div class="bar-meta">meta 7.5</div>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ---- TABLA OT ----
    const tbodyOT = document.getElementById("tablaOT");
    tbodyOT.innerHTML = "";
    tabla.forEach((fila, idx) => {
        const tr = document.createElement("tr");
        tr.dataset.hi = fila.hora_inicio || "";
        const defVal = fila.comentario || "";
        tr.innerHTML = `
            <td><input type="text" class="ot-input inp-ot ${idx === 0 ? 'is-muted' : ''}" value="${escapeHTML(defVal)}" autocomplete="off"></td>
            <td><input type="text" class="ot-input inp-obs" value="${escapeHTML(fila.obs || '')}" autocomplete="off" placeholder="\u2014"></td>
        `;
        tbodyOT.appendChild(tr);
    });
    // Fila vacía adicional
    const trExtra = document.createElement("tr");
    trExtra.innerHTML = `
        <td><input type="text" class="ot-input inp-ot" value="" autocomplete="off"></td>
        <td><input type="text" class="ot-input inp-obs" value="" autocomplete="off" placeholder="\u2014"></td>
    `;
    tbodyOT.appendChild(trExtra);

    // ---- KPIs ----
    const avgIn = data.kpis?.inbound ?? "\u2014";
    const avgOut = data.kpis?.outbound ?? "\u2014";

    animateKPI("kpiIn", avgIn);
    animateKPI("kpiOut", avgOut);

    // Bar widths
    const inNum = parseFloat(avgIn);
    const outNum = parseFloat(avgOut);
    document.getElementById("kpiBarIn").style.width = (!isNaN(inNum) ? Math.min((inNum / 15) * 100, 100) : 0) + "%";
    document.getElementById("kpiBarOut").style.width = (!isNaN(outNum) ? Math.min((outNum / 10) * 100, 100) : 0) + "%";

    // Badges
    const badgeIn = document.getElementById("kpiBadgeIn");
    const badgeOut = document.getElementById("kpiBadgeOut");

    if (!isNaN(inNum)) {
        badgeIn.className = "kpi-card-status " + (inNum >= 11.0 ? "status-ok" : "status-fail");
        badgeIn.textContent = inNum >= 11.0 ? "\u2713 Cumple" : "\u2717 Bajo meta";
    } else {
        badgeIn.className = "kpi-card-status";
        badgeIn.textContent = "";
    }
    if (!isNaN(outNum)) {
        badgeOut.className = "kpi-card-status " + (outNum >= 7.5 ? "status-ok" : "status-fail");
        badgeOut.textContent = outNum >= 7.5 ? "\u2713 Cumple" : "\u2717 Bajo meta";
    } else {
        badgeOut.className = "kpi-card-status";
        badgeOut.textContent = "";
    }
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
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar Reporte';
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
                    toast("Imagen copiada al portapapeles");
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
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar Reporte';
        btn.disabled = false;
    }
}