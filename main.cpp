#include <iostream>
#include <vector>
#include <fstream>
#include <sstream>
#include <cmath>
#include <cstdlib>
#include <string>
#include "silo.hpp"
#include "paletManager.hpp"

// Función auxiliar para cargar el estado inicial del CSV
void cargarEstadoInicial(Silo& silo, const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: No se pudo abrir el archivo " << filename << std::endl;
        return;
    }

    std::string line;
    std::getline(file, line); // Saltar cabecera

    int contador = 0;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;

        std::stringstream ss(line);
        std::string posStr, idStr;
        std::getline(ss, posStr, ',');
        std::getline(ss, idStr, ',');

        if(idStr.empty()) continue;
        
        if (idStr.length() < 15 || posStr.length() < 11) continue; 

        std::string destino = idStr.substr(7, 8);
        Box nuevaCaja(idStr, destino);
        nuevaCaja.pos = Position::fromString(posStr);
        silo.storeBox(nuevaCaja);
        contador++;
    }
    std::cout << "[INFO] Silo inicializado con " << contador << " cajas del CSV: " << filename << "\n";
}

int main(int argc, char* argv[]) {
    // ==================================================================
    // 1. VALORES POR DEFECTO (Se sobreescribirán con la interfaz)
    // ==================================================================
    int totalCajasNuevas = 1200;
    int seed = 42;
    double arrivalRate = 1000.0;
    std::string initialCsv = "silo-semi-empty.csv";
    bool usarABC = true;

    // ==================================================================
    // 2. PARSEADOR DE ARGUMENTOS (Conecta con los botones de Streamlit)
    // ==================================================================
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--cajas" && i + 1 < argc) {
            totalCajasNuevas = std::stoi(argv[++i]);
        } else if (arg == "--seed" && i + 1 < argc) {
            seed = std::stoi(argv[++i]);
        } else if (arg == "--arrival-rate" && i + 1 < argc) {
            arrivalRate = std::stod(argv[++i]);
        } else if (arg == "--initial-csv" && i + 1 < argc) {
            initialCsv = argv[++i];
        } else if (arg == "--abc" && i + 1 < argc) {
            std::string val = argv[++i];
            usarABC = (val == "true" || val == "1");
        }
    }

    // Aplicamos la semilla para que los resultados sean reproducibles en el "A/B Testing" de la interfaz
    srand(seed);

    std::cout << "=== SIMULADOR LOGISTICO C++ ===\n";
    std::cout << "-> Cajas a procesar: " << totalCajasNuevas << "\n";
    std::cout << "-> Arrival Rate: " << arrivalRate << " cajas/h\n";

    Silo miSilo;
    PalletManager manager;
    
    // Generar Shuttles
    std::vector<std::vector<Shuttle>> shuttles;
    for (int a = 1; a <= 4; ++a) {
        std::vector<Shuttle> pasillo;
        for (int y = 1; y <= 8; ++y) {
            pasillo.push_back(Shuttle(a, y));
        }
        shuttles.push_back(pasillo);
    }

    // Aplicar Configuración ABC
    miSilo.loadHistory("historico_pedidos.csv");
    miSilo.setABCStatus(usarABC);

    // Cargar CSV Dinámico desde la interfaz
    if (!initialCsv.empty()) {
        cargarEstadoInicial(miSilo, initialCsv);
    }

    // ==================================================================
    // 3. VARIABLES DE TIEMPO Y SIMULACIÓN
    // ==================================================================
    double globalClock = 0.0;
    // Damos un tiempo máximo muy amplio. Se romperá el bucle cuando ya no haya trabajo.
    const double tiempoMaximo = 20000.0; 
    
    // Calculamos el intervalo exacto (ej. 1000 cajas/h = 1 caja cada 3.6 seg)
    double intervaloEntrada = 3600.0 / arrivalRate; 
    double nextArrivalTime = 0.0; // Reloj específico para la llegada de cajas
    int cajasEntradasRealizadas = 0;

    // Generador de cajas nuevas (Bombo de lotería)
    std::vector<std::string> bomboDestinos;
    std::ifstream fileHist("historico_pedidos.csv");
    std::string lineaHist;
    std::getline(fileHist, lineaHist);
    while (std::getline(fileHist, lineaHist)) {
        if (!lineaHist.empty() && lineaHist.back() == '\r') lineaHist.pop_back();
        if (!lineaHist.empty()) bomboDestinos.push_back(lineaHist);
    }

    std::cout << "[INFO] Iniciando bucle de tiempo real...\n";

    // ==================================================================
    // 4. BUCLE PRINCIPAL DE SIMULACIÓN
    // ==================================================================
    while (globalClock < tiempoMaximo) {
        
        // EVENTO A: Llegada de cajas nuevas (Mejorado para soportar modo "Stress" de interfaz)
        while (globalClock >= nextArrivalTime && cajasEntradasRealizadas < totalCajasNuevas) {
            std::string id = "NEW" + std::to_string(cajasEntradasRealizadas);
            std::string dest = bomboDestinos[rand() % bomboDestinos.size()];
            
            Box tempBox(id, dest);
            Position mejorSitio = miSilo.findBestSlot(tempBox, shuttles);
            
            if (mejorSitio.x != -1) {
                tempBox.pos = mejorSitio;

                // Ocupamos el hueco FÍSICAMENTE al instante para evitar overbooking
                tempBox.isIncoming = true; // Le ponemos la etiqueta para que nadie la toque aún
                miSilo.storeBox(tempBox);

                shuttles[mejorSitio.aisle - 1][mejorSitio.y - 1].pendingInputs.push_back(tempBox);
                cajasEntradasRealizadas++;
            }
            nextArrivalTime += intervaloEntrada; // Programar la siguiente caja
        }

        // EVENTO B: El Manager intenta abrir palets cada 10 segundos
        if (std::fmod(globalClock, 10.0) < 1.0) {
            manager.updateActivePallets(miSilo, globalClock);
        }

        // EVENTO C: Actualizar los 32 Shuttles
        bool shuttlesTrabajando = false;
        for (int a = 0; a < 4; ++a) {
            for (int y = 0; y < 8; ++y) {
                if (shuttles[a][y].totalBusyTime <= globalClock) {
                    shuttles[a][y].totalBusyTime = globalClock;
                    shuttles[a][y].executeNextCycle(miSilo, manager);
                }
                
                // Si un shuttle tiene tareas pendientes O su tiempo futuro es mayor al reloj, está trabajando
                if (shuttles[a][y].getQueueSize() > 0 || shuttles[a][y].totalBusyTime > globalClock) {
                    shuttlesTrabajando = true;
                }
            }
        }

        // EVENTO D: Condición de parada anticipada
        // Si ya entraron todas las cajas, no hay palets activos, y ningún shuttle se está moviendo: ¡FIN!
        if (cajasEntradasRealizadas >= totalCajasNuevas && 
            !manager.hasActivePallets() && 
            !shuttlesTrabajando) {
            break; 
        }

        globalClock += 1.0; 
    }

    // Exportar el JSON que consume la UI
    manager.exportarJSON("output.json", miSilo, globalClock);

    // ==================================================================
    // 5. INFORME FINAL
    // ==================================================================
    std::cout << "\n--- SIMULACION FINALIZADA EN t=" << globalClock << "s ---\n";
    manager.printReport(miSilo, globalClock);

    return 0;
}