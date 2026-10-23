
import os
import re
import requests

from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Batas total upload satu pendaftaran: 16 MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN", "AHUP2hyJ32GrzWzBfmxa")
PIC_NUMBER = os.environ.get("PIC_NUMBER", "6281180895229")

FONNTE_URL = "https://api.fonnte.com/send"

ALLOWED_EXTENSIONS = {
    "schoolLetter": {"pdf",  "png"},
    "studentCard": {"pdf",  "png"},
    "transfer": {"pdf", "png"},
}

SUCCESS_PAGE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Registrasi Catalyst Cup</title>
</head>
<body style="font-family:Arial,sans-serif;text-align:center;padding:40px;">
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <p>Silakan kembali ke website Catalyst Cup.</p>
</body>
</html>
"""


def result_page(title, message, status=200):
    return render_template_string(
        SUCCESS_PAGE, title=title, message=message
    ), status


def valid_file(file, field_name):
    if not file or not file.filename:
        return False

    filename = secure_filename(file.filename)

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS[field_name]


def send_fonnte(message, uploaded_file=None):
    headers = {"Authorization": FONNTE_TOKEN}
    data = {
        "target": PIC_NUMBER,
        "message": message,
    }

    try:
        if uploaded_file:
            uploaded_file.stream.seek(0)

            filename = secure_filename(uploaded_file.filename)

            files = {
                "file": (
                    filename,
                    uploaded_file.stream,
                    uploaded_file.mimetype or "application/octet-stream",
                )
            }

            response = requests.post(
                FONNTE_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=60,
            )
        else:
            response = requests.post(
                FONNTE_URL,
                headers=headers,
                data=data,
                timeout=30,
            )

        response.raise_for_status()
        result = response.json()

        return result.get("status") is True

    except (requests.RequestException, ValueError):
        app.logger.exception("Pengiriman Fonnte gagal")
        return False


@app.route("/", methods=["GET"])
def home():
    return result_page(
        "Backend Catalyst Cup",
        "Backend aktif. Silakan buka website pendaftaran untuk mendaftar."
    )


@app.route("/register/mdsmp", methods=["POST"])
def register_mdsmp():
    if not FONNTE_TOKEN or not PIC_NUMBER:
        app.logger.error("FONNTE_TOKEN atau PIC_NUMBER belum diatur.")
        return result_page(
            "Konfigurasi belum lengkap",
            "Pendaftaran belum dapat diproses. Hubungi panitia.",
            500,
        )

    # Ambil data teks dari form
    players = request.form.get("players", "").strip()
    leader = request.form.get("leader", "").strip()
    responsible = request.form.get("responsible", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()

    # Validasi data wajib
    if not all([players, leader, responsible, phone, email]):
        return result_page(
            "Data belum lengkap",
            "Periksa kembali semua kolom pendaftaran.",
            400,
        )

    if not re.fullmatch(r"08[0-9]{8,11}", phone):
        return result_page(
            "Nomor telepon tidak valid",
            "Masukkan nomor telepon dengan format yang benar.",
            400,
        )

    # Pastikan semua file tersedia dan berekstensi sesuai
    uploaded_files = {}

    for field_name in ALLOWED_EXTENSIONS:
        uploaded_file = request.files.get(field_name)

        if not valid_file(uploaded_file, field_name):
            return result_page(
                "File tidak valid",
                "Pastikan ketiga file sudah dipilih dan formatnya benar.",
                400,
            )

        uploaded_files[field_name] = uploaded_file

    # Kirim informasi pendaftaran terlebih dahulu
    message = (
        "PENDAFTARAN CATALYST CUP VOL 2.0\n"
        "Lomba: Modern Dance SMP\n\n"
        f"Daftar anggota: {players}\n"
        f"Ketua tim: {leader}\n"
        f"Penanggung jawab: {responsible}\n"
        f"No. telepon: {phone}\n"
        f"Email: {email}\n\n"
        "Lampiran akan dikirim melalui pesan berikutnya."
    )

    if not send_fonnte(message):
        return result_page(
            "Pengiriman gagal",
            "Data belum berhasil dikirim. Silakan hubungi panitia.",
            502,
        )

    # Kirim setiap lampiran sebagai pesan terpisah
    labels = {
        "schoolLetter": "Surat Keterangan Sekolah",
        "studentCard": "Foto Kartu Pelajar",
        "transfer": "Bukti Transfer",
    }

    for field_name, uploaded_file in uploaded_files.items():
        attachment_message = (
            "Lampiran pendaftaran Modern Dance SMP\n"
            f"Nama ketua: {leader}\n"
            f"Jenis file: {labels[field_name]}"
        )

        if not send_fonnte(attachment_message, uploaded_file):
            app.logger.error(
                "Gagal mengirim lampiran: %s", field_name
            )
            return result_page(
                "Pengiriman belum lengkap",
                "Sebagian data sudah terkirim, tetapi ada lampiran "
                "yang gagal dikirim. Panitia perlu memeriksanya.",
                502,
            )

    return result_page(
        "Pendaftaran berhasil dikirim!",
        "Data dan seluruh lampiran pendaftaran telah berhasil dikirim "
        "ke layanan WhatsApp. Simpan bukti pendaftaran jika diperlukan.",
    )


@app.errorhandler(413)
def file_too_large(error):
    return result_page(
        "File terlalu besar",
        "Ukuran total file melebihi batas 16 MB.",
        413,
    )


if __name__ == "__main__":
    app.run()

