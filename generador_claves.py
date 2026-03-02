import hashlib
import random
import string

CLAVE_SECRETA = "GUS_POS_2026"

def generar_clave():
    while True:
        partes = []
        for _ in range(3):
            parte = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            partes.append(parte)

        clave = "MPV-" + "-".join(partes)

        texto = clave + CLAVE_SECRETA
        hash_generado = hashlib.sha256(texto.encode()).hexdigest()

        if hash_generado.endswith("00"):
            return clave

print("Clave válida generada:")
print(generar_clave())