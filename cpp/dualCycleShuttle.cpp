#include "silo.hpp"
#include "paletManager.hpp"
#include <iostream>
#include <list>
#include <cmath>
#include <limits>

// Método que ejecuta el siguiente movimiento lógico del Shuttle
void Shuttle::executeNextCycle(Silo& silo, PalletManager& manager) {
    // 1. Verificamos si hay trabajo que hacer en la cola de entrada
    bool hasPendingInputs = !pendingInputs.empty();
    
    // Buscamos si el Silo tiene alguna caja reservada para salir en este pasillo y este nivel Y
    Box* outputBox = silo.findBestBoxToPick(this->aisle, this->currentX, this->levelY);
    bool hasPendingOutputs = (outputBox != nullptr);

    // Si no hay nada que hacer, terminamos el ciclo
    if (!hasPendingInputs && !hasPendingOutputs) {
        // Si el shuttle se quedó a mitad del pasillo, lo devolvemos a cabecera
        if (currentX != 0) {
            // Viaje vacío: t = d (sin operación de carga/descarga)
            totalBusyTime += std::abs(currentX - 0); 
            currentX = 0;
            
        }
        return;
    }

    // ==========================================
    // FASE 1: GESTIÓN DE ENTRADA (Drop en el silo)
    // ==========================================
    if (hasPendingInputs) {
        // Si no estamos en cabecera, tenemos que ir a por la caja primero
        if (currentX != 0) {
            totalBusyTime += currentX; // Viaje vacío a X=0
            currentX = 0;
        }

        // Cogemos la caja de la cola
        Box boxToStore = pendingInputs.front();
        pendingInputs.pop_front();

        int targetX = boxToStore.pos.x;

        // t = 10s cogerla en cabecera + viaje + 10s dejarla en el hueco
        totalBusyTime += 10.0 + targetX + 10.0; 
        
        currentX = targetX;

        // Como ya hemos llegado, le quitamos la etiqueta de "En tránsito"
        // para que el PalletManager ya sepa que puede usarla.
        Box* cajaReal = silo.getBox(boxToStore.pos.aisle, boxToStore.pos.side, targetX, this->levelY, boxToStore.pos.z);
        if (cajaReal != nullptr) {
            cajaReal->isIncoming = false;
        }
        manager.registrarEvento(totalBusyTime, "IN", targetX, this->levelY, boxToStore.pos.z, boxToStore.fullID);
    }

    // ==========================================
    // FASE 2: GESTIÓN DE SALIDA (Pick del silo)
    // ==========================================
    
    // Volvemos a buscar, ya que nuestra posición X ha podido cambiar
    outputBox = silo.findBestBoxToPick(this->aisle, this->currentX, this->levelY);

    if (outputBox != nullptr) {
        int pickX = outputBox->pos.x;
        
        //Extraemos y guardamos el destino
        std::string destination = outputBox->destination;

        std::string cajaID = outputBox->fullID;
        int pickZ = outputBox->pos.z;

        // Viajar hasta la caja a recoger + 10s de operación (Pick)
        int travelToPick = std::abs(pickX - currentX);
        totalBusyTime += 10.0 + travelToPick;
        currentX = pickX;

        // Eliminamos físicamente la caja del almacén
        silo.removeBox(outputBox->pos);

        // (Registramos el evento justo al recogerla)
        manager.registrarEvento(totalBusyTime, "OUT", pickX, this->levelY, pickZ, cajaID);

        // Viajar a cabecera + 10s de operación (Drop en entrada)
        int travelToHead = std::abs(0 - currentX);
        totalBusyTime += 10.0 + travelToHead;

        currentX = 0;

        /*std::cout << "[t=" << totalBusyTime << "s] Shuttle (Pasillo " << aisle << ", Y=" << levelY 
                  << ") extrajo caja de X=" << pickX << " para el palet " << destination << "\n";*/


        // Notificacion
        manager.notifyBoxArrival(destination, totalBusyTime);
        
    } else {

        if (currentX != 0) {
            totalBusyTime += currentX; // Solo sumamos distancia, sin los 10s
            currentX = 0;
        }
    }
}