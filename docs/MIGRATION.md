# Migración a C:\NEXUS_MFP

El paquete fue preparado para ser extraído en:

`C:\NEXUS_MFP`

## Método recomendado
1. Descargar `NEXUS_MFP_MIGRATION.zip` y `MIGRATE_NEXUS_MFP.ps1` a Descargas.
2. Abrir PowerShell.
3. Ejecutar:

```powershell
cd $HOME\Downloads
Set-ExecutionPolicy -Scope Process Bypass
.\MIGRATE_NEXUS_MFP.ps1
```

El script crea `C:\NEXUS_MFP`, extrae el proyecto, crea `.venv`, instala requisitos y abre VS Code si el comando `code` está disponible.

## Después
Abrir `AGENTS.md` en VS Code. Codex debe usarlo como guía del proyecto.
