
/* ==========================================================================
   ChatSphere - QR Code Scanner & Password Controller (qr.js)
   ========================================================================== */

let html5QrcodeScanner = null;
let currentPendingRoomId = null;
let currentPendingInviteUrl = null;

// Start Camera QR Code Scanner
function startQRScanner() {
    const scannerModal = document.getElementById('qr-scanner-modal');
    if (scannerModal) scannerModal.style.display = 'flex';

    if (!html5QrcodeScanner) {
        html5QrcodeScanner = new Html5Qrcode("qr-reader");
    }

    const config = { fps: 10, qrbox: { width: 250, height: 250 } };

    html5QrcodeScanner.start(
        { facingMode: "environment" },
        config,
        onQRCodeScannedSuccess,
        onQRCodeScannedError
    ).catch(err => {
        console.error("Camera access error:", err);
        const errBox = document.getElementById('scanner-error-box');
        if (errBox) {
            errBox.textContent = "Camera access denied or unavailable.";
            errBox.style.display = 'block';
        }
    });
}

function stopQRScanner() {
    if (html5QrcodeScanner) {
        html5QrcodeScanner.stop().then(() => {
            document.getElementById('qr-scanner-modal').style.display = 'none';
        }).catch(err => {
            document.getElementById('qr-scanner-modal').style.display = 'none';
        });
    } else {
        document.getElementById('qr-scanner-modal').style.display = 'none';
    }
}

async function onQRCodeScannedSuccess(decodedText) {
    stopQRScanner();

    // Check if valid token URL
    const match = decodedText.match(/\/join\/invite\/([a-zA-Z0-9_-]+)/);
    if (!match) {
        showInvalidQRModal("Scanned code is not a valid ChatSphere room invitation.");
        return;
    }

    const token = match[1];

    try {
        const res = await fetch(`/api/invite/${token}`);
        const data = await res.json();
        if (data.success) {
            currentPendingRoomId = data.room.id;
            document.getElementById('qr-result-room-name').textContent = data.room.name;
            document.getElementById('qr-result-creator').textContent = '@' + data.room.created_by;
            document.getElementById('qr-result-modal').style.display = 'flex';
        } else {
            showInvalidQRModal(data.message || "Invalid or expired QR invitation.");
        }
    } catch (e) {
        showInvalidQRModal("Failed to connect to server to verify QR code.");
    }
}

function onQRCodeScannedError(errorMessage) {
    // Scanned frame without QR code
}

function showInvalidQRModal(reason) {
    document.getElementById('invalid-qr-reason').textContent = reason;
    document.getElementById('invalid-qr-modal').style.display = 'flex';
}

function continueFromScanPreview() {
    document.getElementById('qr-result-modal').style.display = 'none';
    if (currentPendingRoomId) {
        promptRoomPassword(currentPendingRoomId, document.getElementById('qr-result-room-name').textContent);
    }
}

// Prompt Room Password Modal
function promptRoomPassword(roomId, roomName) {
    currentPendingRoomId = roomId;
    document.getElementById('verify-room-title').textContent = roomName;
    document.getElementById('verify-room-password-input').value = '';
    document.getElementById('verify-error-msg').style.display = 'none';
    document.getElementById('verify-password-modal').style.display = 'flex';
}

async function submitRoomPasswordVerify() {
    const password = document.getElementById('verify-room-password-input').value;
    const errBox = document.getElementById('verify-error-msg');

    if (!password) return;

    try {
        const res = await fetch(`/rooms/${currentPendingRoomId}/verify-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password })
        });
        const data = await res.json();

        if (data.success) {
            window.location.href = data.redirect_url;
        } else {
            errBox.textContent = data.message || "Incorrect room password.";
            errBox.style.display = 'block';
        }
    } catch(e) {
        errBox.textContent = "Server error verifying password.";
        errBox.style.display = 'block';
    }
}

// QR Code Display Modal generator
function showRoomInviteModal(inviteUrl, roomName) {
    currentPendingInviteUrl = inviteUrl;
    document.getElementById('invite-modal-room-name').textContent = roomName;
    document.getElementById('invite-url-input').value = inviteUrl;

    const qrBox = document.getElementById('qrcode-display-box');
    qrBox.innerHTML = '';
    new QRCode(qrBox, {
        text: inviteUrl,
        width: 180,
        height: 180
    });

    document.getElementById('qr-invite-modal').style.display = 'flex';
}

function downloadQRImage() {
    const qrCanvas = document.querySelector('#qrcode-display-box canvas');
    if (qrCanvas) {
        const link = document.createElement('a');
        link.download = `chatsphere-room-invite-qr.png`;
        link.href = qrCanvas.toDataURL('image/png');
        link.click();
    }
}

async function regenerateInvite(roomId) {
    if (!confirm("Regenerating the QR code will invalidate all previous invitations. Proceed?")) return;

    try {
        const res = await fetch(`/rooms/${roomId}/regenerate-invite`, { method: 'POST' });
        const data = await res.json();
        alert(data.message);
        if (data.success) {
            showRoomInviteModal(data.invite_url, document.getElementById('invite-modal-room-name').textContent);
        }
    } catch(e) {
        alert("Failed to regenerate invite QR.");
    }
}
