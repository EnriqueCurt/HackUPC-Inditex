#include "paletManager.hpp"


void PalletManager::updateActivePallets(Silo& silo, double currentTime) {
    if (activePallets.size() >= MAX_ACTIVE_PALLETS) return;

    // Pedimos al silo la lista de todas las cajas que tiene guardadas
    std::vector<Box*> allBoxes = silo.getAllBoxes();
    std::map<std::string, int> inventoryCount;

    // 1. Contar cajas disponibles (que no estén ya reservadas)
    for (Box* box : allBoxes) {
        if (!box->isReserved) {
            inventoryCount[box->destination]++;
        }
    }

    // 2. Buscar destinos que tengan >= 12 cajas
    for (const auto& pair : inventoryCount) {
        if (pair.second >= 12 && activePallets.size() < MAX_ACTIVE_PALLETS) {
            
            std::string selectedDestination = pair.first;
            
            // 3. Creamos el nuevo palet activo
            ActivePallet newPallet;
            newPallet.destination = selectedDestination;
            
            // Guardamos la hora a la que empezamos a formar el palet ---
            newPallet.startTime = currentTime; 
            
            activePallets.push_back(newPallet);

            // 4. Reservar exactamente 12 cajas de ese destino
            int boxesReserved = 0;
            for (Box* box : allBoxes) {
                if (box->destination == selectedDestination && !box->isReserved) {
                    box->isReserved = true;
                    boxesReserved++;
                    if (boxesReserved == 12) break;
                }
            }
            
            /*std::cout << "Manager: Nuevo palet reservado para [" << selectedDestination 
                      << "] en t=" << currentTime << "s\n";*/
        }
    }
}

void PalletManager::notifyBoxArrival(std::string dest, double arrivalTime) {
    for (auto it = activePallets.begin(); it != activePallets.end(); ++it) {
        if (it->destination == dest) {
            it->currentBoxes++;
            
            // El tiempo de fin del palet se actualiza con cada caja.
            // Al final, quedará registrado el tiempo de la más lenta.
            if (arrivalTime > it->completionTime) {
                it->completionTime = arrivalTime;
            }

            if (it->currentBoxes >= it->targetBoxes) {
                /*std::cout << "¡PALET COMPLETADO! Destino: " << dest 
                          << " | Tiempo total: " << (it->completionTime - it->startTime) << "s\n";*/
                completedPallets.push_back(*it);
                activePallets.erase(it);
                break;
            }
        }
    }
}

void PalletManager::printReport() const {
    std::cout << "\n========================================================\n";
    std::cout << "          REPORTE FINAL DE RENDIMIENTO (INDITEX)          \n";
    std::cout << "========================================================\n";
    
    double totalCycleTime = 0.0;

    if (completedPallets.empty()) {
        std::cout << "  No se completó ningún palet.\n";
    } else {
        for (const auto& p : completedPallets) {
            double cycle = p.completionTime - p.startTime;
            totalCycleTime += cycle;
        }
    }
    
    std::cout << "\n------------------- METRICAS CLAVE ---------------------\n";
    
    int totalPalets = completedPallets.size();
    std::cout << "[1] TOTAL DE PALETS COMPLETADOS : " << totalPalets << " palets\n";
    std::cout << "[2] TOTAL DE CAJAS EXTRAIDAS    : " << (totalPalets * 12) << " cajas\n";
    
    if (totalPalets > 0) {
        double averageTime = totalCycleTime / totalPalets;
        std::cout << "[3] THROUGHPUT (Tiempo Medio)   : " << averageTime << " s/palet\n";
    }

    // Nuestro sistema tiene una regla estricta de no sacar palets a medias, 
    // por lo tanto, la métrica de Full Pallets siempre es el 100% de lo extraído.
    std::cout << "[4] FULL PALLETS PERCENTAGE     : 100 %\n";
    std::cout << "========================================================\n";
}

#include <fstream>
#include <iomanip>

// Pon esto al final de paletManager.cpp
void PalletManager::exportarJSON(const std::string& filename, double tiempoTotalSimulacion) const {
    std::ofstream out(filename);
    if (!out.is_open()) {
        std::cerr << "Error al crear el archivo JSON.\n";
        return;
    }

    // 1. Cálculos de métricas
    int paletsCompletados = completedPallets.size();
    double throughput = 0.0;
    if (tiempoTotalSimulacion > 0) {
        // Palets por hora
        throughput = (paletsCompletados / tiempoTotalSimulacion) * 3600.0; 
    }
    
    // Un score inventado para el hackathon (ej: premia palets completados y penaliza tiempo)
    int score = (paletsCompletados * 1000) - static_cast<int>(tiempoTotalSimulacion);
    if (score < 0) score = 0;

    // Empezamos a escribir el JSON
    out << std::fixed << std::setprecision(2);
    out << "{\n";
    
    // --- METRICS ---
    out << "  \"metrics\": {\n"
        << "    \"t_simulacion_s\": " << tiempoTotalSimulacion << ",\n"
        << "    \"throughput_palets_hora\": " << throughput << ",\n"
        << "    \"palets_completados\": " << paletsCompletados << ",\n"
        << "    \"tasa_completitud_%\": 100.0,\n" // Como no dejamos palets a medias, es 100%
        << "    \"score\": " << score << "\n"
        << "  },\n";

    // --- PALLETS ---
    out << "  \"pallets\": [\n";
    for (size_t i = 0; i < completedPallets.size(); ++i) {
        const auto& p = completedPallets[i];
        out << "    {\"id_destino\": \"" << p.destination 
            << "\", \"t_fin\": " << p.completionTime 
            << ", \"total_cajas\": " << p.targetBoxes << "}";
        if (i < completedPallets.size() - 1) out << ",";
        out << "\n";
    }
    out << "  ],\n";

    // --- EVENTS ---
    out << "  \"events\": [\n";
    for (size_t i = 0; i < historialEventos.size(); ++i) {
        const auto& e = historialEventos[i];
        out << "    {\"t\": " << e.t 
            << ", \"tipo\": \"" << e.tipo 
            << "\", \"x\": " << e.x 
            << ", \"y\": " << e.y 
            << ", \"z\": " << e.z 
            << ", \"caja\": \"" << e.caja << "\"}";
        if (i < historialEventos.size() - 1) out << ",";
        out << "\n";
    }
    out << "  ]\n";

    out << "}\n";
    out.close();
    
    std::cout << "[SISTEMA] Archivo '" << filename << "' generado con exito para la Interfaz Grafica.\n";
}