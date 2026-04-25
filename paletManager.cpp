#include "paletManager.hpp"
#include <iostream>

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
            
            std::cout << "Manager: Nuevo palet reservado para [" << selectedDestination 
                      << "] en t=" << currentTime << "s\n";
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
                std::cout << "¡PALET COMPLETADO! Destino: " << dest 
                          << " | Tiempo total: " << (it->completionTime - it->startTime) << "s\n";
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