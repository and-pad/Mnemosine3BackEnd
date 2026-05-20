FROM python:3.12-slim

WORKDIR /mnemikon

RUN apt update && apt install -y \
    pandoc \
    texlive-latex-base \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra \
    lmodern \
    && apt clean

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "MnemosineV3_0.wsgi:application", "--bind", "0.0.0.0:8000"]
