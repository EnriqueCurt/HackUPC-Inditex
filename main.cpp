#include <iostream>
#include <vector>
#include <fstream>
#include <sstream>
#include <cmath>
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
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::string posStr, idStr;
        std::getline(ss, posStr, ',');
        std::getline(ss, idStr, ',');

        // Extraemos destino (dígitos 8 al 15 del ID de 20 dígitos)
        std::string destino = idStr.substr(7, 8);
        
        Box nuevaCaja(idStr, destino);
        nuevaCaja.pos = Position::fromString(posStr);
        
        silo.storeBox(nuevaCaja);
        contador++;
    }
    std::cout << "[INFO] Silo inicializado con " << contador << " cajas del CSV.\n";
}

int main() {
    std::cout << "=== SIMULADOR LOGISTICO DE ALTO RENDIMIENTO ===\n\n";

    // 1. Inicialización de componentes
    Silo miSilo;
    PalletManager manager;
    
    // Matriz de 32 Shuttles: [Pasillo 0-3][Nivel 0-7]
    std::vector<std::vector<Shuttle>> shuttles;
    for (int a = 1; a <= 4; ++a) {
        std::vector<Shuttle> pasillo;
        for (int y = 1; y <= 8; ++y) {
            pasillo.push_back(Shuttle(a, y));
        }
        shuttles.push_back(pasillo);
    }

    // 2. Cargar el escenario inicial (el CSV que nos dieron)
    cargarEstadoInicial(miSilo, "silo-semi-empty.csv");

    // 3. Variables de simulación
    double globalClock = 0.0;
    const double tiempoMaximo = 3600.0; // Simulamos 1 hora
    const double intervaloEntrada = 3.6; // 1000 cajas/hora ≈ 1 cada 3.6s
    int cajasEntradasRealizadas = 0;
    const int totalCajasNuevas = 200; // Por ejemplo, 200 cajas nuevas online

    std::cout << "[INFO] Iniciando bucle de tiempo real...\n";

    // 4. Bucle principal de Simulación
    // El bucle sigue mientras no pase la hora O queden palets activos
    while (globalClock < tiempoMaximo) {
        
        // EVENTO A: Llegada de caja nueva (Online Arrival)
        if (std::fmod(globalClock, intervaloEntrada) < 1.0 && cajasEntradasRealizadas < totalCajasNuevas) {
            // Generamos un ID y destino de prueba (simulando llegada real)
            std::string id = "NEW" + std::to_string(cajasEntradasRealizadas);
            std::string dest = "01018310"; // Destino frecuente en el CSV
            
            Box tempBox(id, dest);
            
            // Buscamos el mejor hueco entre los 32 shuttles
            Position mejorSitio = miSilo.findBestSlot(tempBox, shuttles);
            
            if (mejorSitio.x != -1) {
                tempBox.pos = mejorSitio;
                // Encolamos la entrada en el shuttle correspondiente
                shuttles[mejorSitio.aisle - 1][mejorSitio.y - 1].pendingInputs.push_back(tempBox);
                cajasEntradasRealizadas++;
            }
        }

        // EVENTO B: El Manager intenta abrir palets cada 10 segundos
        if (std::fmod(globalClock, 10.0) < 1.0) {
            manager.updateActivePallets(miSilo, globalClock);
        }

        // EVENTO C: Actualizar los 32 Shuttles
        for (int a = 0; a < 4; ++a) {
            for (int y = 0; y < 8; ++y) {
                // Si el shuttle ha terminado su tarea anterior (su reloj <= reloj global)
                if (shuttles[a][y].totalBusyTime <= globalClock) {
                    // Sincronizamos el tiempo del shuttle con el global antes de darle la siguiente tarea
                    shuttles[a][y].totalBusyTime = globalClock;
                    shuttles[a][y].executeNextCycle(miSilo, manager);
                }
            }
        }
        // Avanzamos el reloj (puedes aumentar el paso para que la simulación vuele)
        globalClock += 1.0; 
    }

    // 5. Informe Final
    std::cout << "\n--- SIMULACION FINALIZADA EN t=" << globalClock << "s ---\n";
    manager.printReport();

    return 0;
}