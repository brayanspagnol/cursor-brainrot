# Brainrot

Abre TikTok, Instagram Reels e YouTube Shorts em 3 janelas enquanto o Cursor pensa. Fecha só essas janelas quando o agente termina.

## Instalação

**Requisitos:** Cursor, Python 3.10+, Chrome/Brave/Edge

```bash
git clone https://github.com/brayanspagnol/brainrot.git
cd brainrot
python3 brainrot.py install      # Linux
# py -3 .\brainrot.py install   # Windows
```

Reinicie o Cursor se os hooks não dispararem.

## Login

Usa o **mesmo perfil** do seu Brave/Chrome — se você já está logado no navegador, as janelas do brainrot também vêm logadas.

O `close` fecha **somente** as 3 janelas do brainrot. O resto do browser continua aberto.

## Uso

```bash
python3 brainrot.py open
python3 brainrot.py close
```

Para mudar os sites, edite `URLS` em `brainrot.py`.

## Desinstalar

```bash
python3 brainrot.py uninstall
```
