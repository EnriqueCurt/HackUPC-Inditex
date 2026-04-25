#ifndef PALLET_MANAGER_HPP
#define PALLET_MANAGER_HPP

#include <string>
#include <vector>
#include <map>
#include "silo.hpp"

struct ActivePallet {
    std::string destination;
    int currentBoxes = 0; // Cajas ya extraídas y puestas en el palet físico
    int targetBoxes = 12; // La regla del enunciado
    double startTime = 0.0;
    double completionTime = 0.0;
};

class PalletManager {
private:
    std::vector<ActivePallet> activePallets;
    std::vector<ActivePallet> completedPallets; //Historial para el reporte
    const int MAX_ACTIVE_PALLETS = 8; // Las 2 posiciones x 4 palets de los robots

public:
    // Revisa el inventario y activa palets si hay hueco
    void updateActivePallets(Silo& silo, double currentTime);
    
    // Función auxiliar para contar cajas no reservadas de un destino
    int countAvailableBoxes(const Silo& silo, const std::string& destination);

    // Método para notificar que una caja ha llegado a X=0
    void notifyBoxArrival(std::string dest, double arrivalTime);

    void printReport() const;

    bool hasActivePallets() const {return !activePallets.empty();}
};

#endif