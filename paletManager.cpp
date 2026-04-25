#include "paletManager.hpp"
#include <iostream>

void PalletManager::updateActivePallets(Silo& silo, double currentTime) { // <-- ¡Añadido aquí!
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
            
            // 3. Crear el nuevo palet activo
            ActivePallet newPallet;
            newPallet.destination = selectedDestination;
            
            // --- NUEVO: Guardamos la hora a la que empezamos a formar el palet ---
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
    std::cout << "\n============================================\n";
    std::cout << "       REPORTE FINAL DE RENDIMIENTO           \n";
    std::cout << "============================================\n";
    for (const auto& p : completedPallets) {
        std::cout << "- Palet [" << p.destination << "]\n"
                  << "  Inicio: " << p.startTime << "s | Fin: " << p.completionTime << "s\n"
                  << "  Tiempo Ciclo Total: " << (p.completionTime - p.startTime) << "s\n";
    }
    std::cout << "============================================\n";
}