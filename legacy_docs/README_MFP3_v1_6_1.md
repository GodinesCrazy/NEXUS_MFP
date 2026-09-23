# MFP-3 v1.6.1

Corrección de compatibilidad con pandas 2.1.x.

## Cambio
La línea de Monte Carlo:

```python
resample("ME")
```

se cambió por:

```python
resample("M")
```

porque pandas 2.1.1 no reconoce `ME`.

## Ejecutar

Guarda `mfp3_robust_time_machine_v1_6_1.py` en Descargas y ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_robust_time_machine_v1_6_1.py
```

No necesitas reinstalar ninguna librería.
