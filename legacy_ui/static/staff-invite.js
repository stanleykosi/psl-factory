"use strict";

const code = window.location.hash.slice(1);
if (/^[A-Za-z0-9_-]{43}$/.test(code)) {
    document.getElementById("id_token").value = code;
    window.history.replaceState(null, "", window.location.pathname);
}
