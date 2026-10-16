// L'application du téléphone (R3) : écrire ou maintenir le bouton pour parler à Friday (le
// Raspberry Pi, par Tailscale) ; ses réponses arrivent au fil de l'eau et sont lues par la
// voix française du téléphone, phrase par phrase.
"use strict";
const $ = (id) => document.getElementById(id);
const fil = $("fil"), etat = $("etat"), texte = $("texte"), micro = $("micro");
const envoyer = $("envoyer"), son = $("son"), aide = $("aide");
let occupe = false, enregistreur = null, morceaux = [], debut = 0, flux = null;

function retenu(cle, defaut) {  // une préférence de ce téléphone (peut être indisponible)
  try { const v = localStorage.getItem(cle); return v === null ? defaut : v === "1"; }
  catch (e) { return defaut; }
}
function retenir(cle, oui) { try { localStorage.setItem(cle, oui ? "1" : "0"); } catch (e) {} }

function montrer(message, ms = 2200) {
  aide.textContent = message;
  aide.classList.add("voir");
  clearTimeout(montrer.t);
  montrer.t = setTimeout(() => aide.classList.remove("voir"), ms);
}
function bulle(classe, contenu = "") {
  fil.querySelector(".vide")?.remove();
  const el = document.createElement("div");
  el.className = classe;
  el.textContent = contenu;
  fil.append(el);
  fil.scrollTop = fil.scrollHeight;
  return el;
}
function signaler(classe, message) { etat.className = classe; etat.textContent = message; }

// --- La voix du téléphone -------------------------------------------------------------
let parole = retenu("son", true), voix = null, reste = "";
function choisirVoix() {
  const toutes = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("fr"));
  voix = toutes.find((v) => /google/i.test(v.name)) || toutes[0] || null;
}
if ("speechSynthesis" in window) {
  choisirVoix();
  speechSynthesis.onvoiceschanged = choisirVoix;
}
function dire(phrase) {
  if (!parole || !("speechSynthesis" in window) || !phrase.trim()) return;
  const u = new SpeechSynthesisUtterance(phrase.trim());
  u.lang = "fr-FR";
  if (voix) u.voice = voix;
  speechSynthesis.speak(u);
}
function lirePhrases(morceau, fin = false) {  // une phrase complète part dès qu'elle est finie
  reste += morceau;
  const phrases = reste.match(/[^.!?…]+[.!?…]+["»)]?\s*/g) || [];
  const lues = phrases.join("");
  phrases.forEach(dire);
  reste = reste.slice(lues.length);
  if (fin) { dire(reste); reste = ""; }
}
function debloquerVoix() {  // Android : la voix doit d'abord servir pendant un geste
  if (!("speechSynthesis" in window) || debloquerVoix.fait) return;
  speechSynthesis.speak(new SpeechSynthesisUtterance(""));
  debloquerVoix.fait = true;
}
son.setAttribute("aria-pressed", String(parole));
son.onclick = () => {
  parole = !parole;
  retenir("son", parole);
  son.setAttribute("aria-pressed", String(parole));
  if (!parole) speechSynthesis.cancel();
  montrer(parole ? "Réponses lues à voix haute" : "Réponses en silence");
};

// --- Une demande au Pi, et sa réponse ligne par ligne ---------------------------------
function attendre(occupeMaintenant) {
  occupe = occupeMaintenant;
  micro.disabled = envoyer.disabled = occupe;
  clearInterval(attendre.t);
  if (!occupe) { signaler("ok", "prête"); return; }
  const depuis = Date.now();
  const tic = () => signaler("busy", `réfléchit · ${Math.round((Date.now() - depuis) / 1000)} s`);
  tic();
  attendre.t = setInterval(tic, 1000);
}
async function demander(adresse, corps, type) {
  attendre(true);
  window.speechSynthesis?.cancel();
  let reponse = null, attente = bulle("msg friday attente", "…");
  try {
    const r = await fetch(adresse, {method: "POST", headers: {"Content-Type": type}, body: corps});
    if (!r.ok) throw new Error(r.status === 401 ? "accès refusé" : `erreur ${r.status}`);
    const lecteur = r.body.getReader(), decodeur = new TextDecoder();
    let tampon = "";
    for (;;) {
      const {value, done} = await lecteur.read();
      if (done) break;
      tampon += decodeur.decode(value, {stream: true});
      let i;
      while ((i = tampon.indexOf("\n")) >= 0) {
        const ligne = tampon.slice(0, i).trim();
        tampon = tampon.slice(i + 1);
        if (!ligne) continue;
        const d = JSON.parse(ligne);
        if (d.vous) { attente.before(bulle("msg vous", d.vous)); fil.append(attente); }
        if (d.outil) { fil.insertBefore(bulle("outil", d.outil), attente); }
        if (d.texte) {
          if (!reponse) { reponse = attente; reponse.className = "msg friday"; reponse.textContent = ""; }
          reponse.textContent += d.texte;
          lirePhrases(d.texte);
          fil.scrollTop = fil.scrollHeight;
        }
        if (d.erreur) { attente.className = "msg friday erreur"; attente.textContent = d.erreur; dire(d.erreur); }
        if (d.fin) lirePhrases("", true);
      }
    }
    attendre(false);
  } catch (e) {
    attente.className = "msg friday erreur";
    attente.textContent = "Le Pi ne répond pas (" + e.message + "). Tailscale est-il activé ?";
    attendre(false);
    signaler("off", "injoignable");
  }
}
function envoyerTexte() {
  const t = texte.value.trim();
  if (!t || occupe) return;
  debloquerVoix();
  bulle("msg vous", t);
  texte.value = "";
  texte.style.height = "";
  demander("/api/message", JSON.stringify({texte: t}), "application/json");
}
envoyer.onclick = envoyerTexte;
texte.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyerTexte(); }
});
texte.addEventListener("input", () => {
  texte.style.height = "";
  texte.style.height = Math.min(texte.scrollHeight, 120) + "px";
});
$("nouvelle").onclick = async () => {
  if (occupe) return;
  await fetch("/api/nouvelle", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
  fil.replaceChildren();
  bulle("vide", "Nouvelle conversation.");
};

// --- Le bouton à maintenir : on parle tant qu'il est appuyé ---------------------------
async function commencer(e) {
  e.preventDefault();
  if (occupe || enregistreur) return;
  debloquerVoix();
  window.speechSynthesis?.cancel();
  try {
    flux = flux || await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
  } catch (err) {
    montrer("Micro refusé : autorisez-le pour cette page.", 3500);
    return;
  }
  morceaux = [];
  const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  enregistreur = new MediaRecorder(flux, type ? {mimeType: type} : {});
  enregistreur.ondataavailable = (ev) => { if (ev.data.size) morceaux.push(ev.data); };
  enregistreur.start();
  debut = Date.now();
  micro.classList.add("ecoute");
  montrer("J'écoute… relâchez pour envoyer", 60000);
}
function finir(annuler) {
  if (!enregistreur) return;
  const rec = enregistreur, duree = Date.now() - debut;
  enregistreur = null;
  micro.classList.remove("ecoute");
  aide.classList.remove("voir");
  rec.onstop = () => {
    flux?.getTracks().forEach((t) => t.stop());  // le micro se coupe entre deux phrases
    flux = null;
    if (annuler) return;
    if (duree < 500) { montrer("Maintenez le bouton pendant que vous parlez."); return; }
    demander("/api/audio", new Blob(morceaux, {type: rec.mimeType || "audio/webm"}), rec.mimeType || "audio/webm");
  };
  rec.stop();
}
micro.addEventListener("pointerdown", commencer);
micro.addEventListener("pointerup", () => finir(false));
micro.addEventListener("pointercancel", () => finir(true));
micro.addEventListener("contextmenu", (e) => e.preventDefault());

// --- Au lancement -----------------------------------------------------------------------
fetch("/api/etat").then((r) => r.ok ? r.json() : Promise.reject(r.status))
  .then(() => signaler("ok", "prête"))
  .catch((s) => signaler("off", s === 401 ? "accès refusé" : "injoignable"));
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
