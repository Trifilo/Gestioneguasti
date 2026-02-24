
import { spawn } from "child_process";

// Questo script funge da bridge per avviare l'applicazione Python Flask
// quando l'ambiente Replit esegue "npm run dev".
// Sostituisce il server Node.js originale per questo progetto Python.

console.log("--------------------------------------------------");
console.log("   AVVIO SERVER PYTHON FLASK (Progetto Scolastico)");
console.log("--------------------------------------------------");

const pythonProcess = spawn("python", ["app.py"], {
  stdio: "inherit",
  shell: true,
});

pythonProcess.on("close", (code) => {
  console.log(`Processo Python terminato con codice ${code}`);
  process.exit(code ?? 0);
});

// Gestione segnali di terminazione per chiudere anche Python
process.on("SIGINT", () => {
  pythonProcess.kill("SIGINT");
  process.exit(0);
});

process.on("SIGTERM", () => {
  pythonProcess.kill("SIGTERM");
  process.exit(0);
});
