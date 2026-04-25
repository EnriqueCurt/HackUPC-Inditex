#include "paletManager.hpp"


void PalletManager::updateActivePallets(Silo& silo, double currentTime) {
    if (activePallets.size() >= MAX_ACTIVE_PALLETS) return;

    // Pedimos al silo la lista de todas las cajas que tiene guardadas
    std::vector<Box*> allBoxes = silo.getAllBoxes();
    std::map<std::string, int> inventoryCount;

    // 1. Contar cajas disponibles (que no estén ya reservadas)
    for (Box* box : allBoxes) {
        if (!box->isReserved && !box -> isIncoming) {
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

void PalletManager::printReport(const Silo& silo, double totalSimTime) const {
    std::cout << "\n========================================================\n";
    std::cout << "          REPORTE FINAL DE RENDIMIENTO (INDITEX)          \n";
    std::cout << "========================================================\n";
    
    int totalPalets = completedPallets.size();
    std::vector<double> cycleTimes;
    double totalCycleTime = 0.0;

    for (const auto& p : completedPallets) {
        double cycle = p.completionTime - p.startTime;
        cycleTimes.push_back(cycle);
        totalCycleTime += cycle;
    }

    // --- CÁLCULOS ESTADÍSTICOS ---
    double averageTime = 0.0;
    double medianTime = 0.0;
    double palletsPerHour = 0.0;

    if (totalPalets > 0) {
        // Media
        averageTime = totalCycleTime / totalPalets;

        // Mediana
        std::sort(cycleTimes.begin(), cycleTimes.end());
        if (totalPalets % 2 == 0) {
            medianTime = (cycleTimes[totalPalets / 2 - 1] + cycleTimes[totalPalets / 2]) / 2.0;
        } else {
            medianTime = cycleTimes[totalPalets / 2];
        }

        // Palets / Hora
        if (totalSimTime > 0) {
            palletsPerHour = (totalPalets / totalSimTime) * 3600.0;
        }
    }

    // Cajas sobrantes en el Silo
    int cajasEnSilo = silo.getAllBoxes().size();

    std::cout << "\n------------------- METRICAS CLAVE ---------------------\n";
    std::cout << "[1] TOTAL DE PALETS COMPLETADOS : " << totalPalets << " palets\n";
    std::cout << "[2] TOTAL DE CAJAS EXTRAIDAS    : " << (totalPalets * 12) << " cajas\n";
    std::cout << "[3] CAJAS RESTANTES EN SILO     : " << cajasEnSilo << " cajas\n";
    std::cout << "[4] THROUGHPUT (Palets / Hora)  : " << palletsPerHour << " palets/h\n";
    std::cout << "[5] TIEMPO MEDIO (Average)      : " << averageTime << " s/palet\n";
    std::cout << "[6] MEDIANA DE TIEMPO (Median)  : " << medianTime << " s/palet\n";
    std::cout << "[7] FULL PALLETS PERCENTAGE     : 100 %\n";
    std::cout << "========================================================\n";
}

void PalletManager::exportarJSON(const std::string& filename, const Silo& silo, double tiempoTotalSimulacion) const {

    std::ofstream out(filename);
    
    if (!out.is_open()) {
        std::cerr << "Error al crear el archivo JSON.\n";
        return;
    }

    // --- CÁLCULOS PREVIOS ---
    int paletsCompletados = completedPallets.size();
    std::vector<double> cycleTimes;
    double totalCycleTime = 0.0;

    for (const auto& p : completedPallets) {
        double cycle = p.completionTime - p.startTime;
        cycleTimes.push_back(cycle);
        totalCycleTime += cycle;
    }

    double averageTime = 0.0;
    double medianTime = 0.0;
    double throughput = 0.0;

    if (paletsCompletados > 0) {
        averageTime = totalCycleTime / paletsCompletados;

        // Cálculo de Mediana
        std::sort(cycleTimes.begin(), cycleTimes.end());
        if (paletsCompletados % 2 == 0) {
            medianTime = (cycleTimes[paletsCompletados / 2 - 1] + cycleTimes[paletsCompletados / 2]) / 2.0;
        } else {
            medianTime = cycleTimes[paletsCompletados / 2];
        }

        if (tiempoTotalSimulacion > 0) {
            throughput = (paletsCompletados / tiempoTotalSimulacion) * 3600.0;
        }
    }

    int cajasRestantes = silo.getAllBoxes().size();
    int score = (paletsCompletados * 1000) + (cajasRestantes * -10); // Ejemplo de score: premia palets, penaliza stock parado

    // --- GENERACIÓN DEL JSON ---
    out << std::fixed << std::setprecision(2);
    out << "{\n";
    
    out << "  \"metrics\": {\n"
        << "    \"t_simulacion_s\": " << tiempoTotalSimulacion << ",\n"
        << "    \"throughput_palets_hora\": " << throughput << ",\n"
        << "    \"palets_completados\": " << paletsCompletados << ",\n"
        << "    \"tasa_completitud_%\": 100.0,\n"
        << "    \"score\": " << score << ",\n"
        << "    \"cajas_restantes_silo\": " << cajasRestantes << ",\n" // NUEVA
        << "    \"tiempo_medio_s_palet\": " << averageTime << ",\n"    // NUEVA
        << "    \"mediana_tiempo_s_palet\": " << medianTime << "\n"    // NUEVA
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