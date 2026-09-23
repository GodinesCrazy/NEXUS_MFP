# MFP-3 ONE FILE v1.9

La v1.9 mantiene el principio de **un solo archivo**.

## Uso normal

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_9.py
```

Además de todo lo que ya hacía v1.8, ahora:

- clasifica noticias por categoría;
- mide novedad/duplicación de titulares;
- calcula intensidad de evento;
- detecta régimen de mercado;
- aprende impacto por categoría y activo;
- calcula presión informativa de las últimas 48 horas;
- hace health-check;
- crea backup diario y conserva los últimos 7;
- puede instalarse en el Programador de tareas de Windows.

## Automatizar

```powershell
py mfp3_onefile_v1_9.py --install
```

Instala una tarea diaria a las 18:30.

## Desinstalar automatización

```powershell
py mfp3_onefile_v1_9.py --uninstall
```

## Health check

```powershell
py mfp3_onefile_v1_9.py --health
```

## Status breve

```powershell
py mfp3_onefile_v1_9.py --status
```

## Forzar recálculo completo

```powershell
py mfp3_onefile_v1_9.py --full
```

No ejecuta operaciones reales.
