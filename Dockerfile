FROM python:3.12-slim

WORKDIR /mnemikon

# =========================
# SYSTEM DEPENDENCIES
# =========================
RUN apt update && apt install -y \
    pandoc \
    texlive-latex-base \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra \
    lmodern \
    gcc \
    && apt clean && rm -rf /var/lib/apt/lists/*

# =========================
# PYTHON DEPENDENCIES
# =========================
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# =========================
# PROJECT FILES
# =========================
COPY . .

# =========================
# DJANGO/GUNICORN
# =========================
EXPOSE 8000

CMD ["gunicorn", \
    "MnemosineV3_0.wsgi:application", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "3", \
    "--threads", "4", \
    "--timeout", "1200", \
    "--graceful-timeout", "30", \
    "--keep-alive", "5", \
    "--log-level", "info"]
