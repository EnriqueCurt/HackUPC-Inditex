#include <iostream>
#include <vector>
#include <fstream>
#include <sstream>
#include <cmath>
#include <cstdlib>
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
        // 1. ESCUDO: Limpiar caracteres 'fantasma' de Windows (\r)
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Si la línea está vacía tras limpiarla, la ignoramos
        if (line.empty()) continue;

        std::stringstream ss(line);
        std::string posStr, idStr;
        std::getline(ss, posStr, ',');
        std::getline(ss, idStr, ',');

        // 2. ESCUDO: Validar que los datos leídos tienen la longitud mínima esperada
        // El ID debe tener al menos 15 caracteres
        // La posición debe tener 11 caracteres para el fromString
        if(idStr.empty()){
            continue;
        }
        if (idStr.length() < 15 || posStr.length() < 11) {
            std::cerr << "Aviso: Linea ignorada por formato incorrecto -> " << line << "\n";
            continue; 
        }

        // Ahora sí podemos extraer de forma 100% segura
        std::string destino = idStr.substr(7, 8);
        
        Box nuevaCaja(idStr, destino);
        nuevaCaja.pos = Position::fromString(posStr);
        
        silo.storeBox(nuevaCaja);
        contador++;
    }
    std::cout << "[INFO] Silo inicializado con " << contador << " cajas del CSV.\n";
}

int main(int argc, char* argv[]) {
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

    // Entrenar al algoritmo con el historico
    miSilo.loadHistory("historico_pedidos.csv");
    
    // Leemos la terminal para ver si nos han pasado el argumento "--abc"
    bool usarABC = false; 
    if (argc > 1) {
        std::string argumento = argv[1];
        if (argumento == "--abc") {
            usarABC = true;
        }
    }
    
    // Le pasamos la decisión al Silo
    miSilo.setABCStatus(usarABC);

    // 2. Cargar el escenario inicial (el CSV que nos dieron)
    cargarEstadoInicial(miSilo, "silo-semi-empty.csv");

    // 3. Variables de simulación
    double globalClock = 0.0;
    const double tiempoMaximo = 8000.0; // Simulamos 1 hora
    const double intervaloEntrada = 3.6; // 1000 cajas/hora ≈ 1 cada 3.6s
    int cajasEntradasRealizadas = 0;
    const int totalCajasNuevas = 1200; 

    // Generador de cajas nuevas
    std::vector<std::string> bomboDestinos;
    std::ifstream fileHist("historico_pedidos.csv");
    std::string lineaHist;
    std::getline(fileHist, lineaHist); // Saltar cabecera
    while (std::getline(fileHist, lineaHist)) {
        if (!lineaHist.empty() && lineaHist.back() == '\r') lineaHist.pop_back();
        if (!lineaHist.empty()) bomboDestinos.push_back(lineaHist);
    }

    std::cout << "[INFO] Iniciando bucle de tiempo real...\n";

    
    // 4. Bucle principal de Simulación
    // El bucle sigue mientras no pase la hora O queden palets activos
    while (globalClock < tiempoMaximo) {
        
        // EVENTO A: Llegada de caja nueva (Online Arrival)
        if (std::fmod(globalClock, intervaloEntrada) < 1.0 && cajasEntradasRealizadas < totalCajasNuevas) {
            // Generamos un ID y destino de prueba (simulando llegada real)
            std::string id = "NEW" + std::to_string(cajasEntradasRealizadas);
            std::string dest = bomboDestinos[rand() % bomboDestinos.size()];
            
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

    // Generar el archivo JSON para el Frontend
    manager.exportarJSON("output.json", globalClock);

    // 5. Informe Final
    std::cout << "\n--- SIMULACION FINALIZADA EN t=" << globalClock << "s ---\n";
    manager.printReport();

    return 0;
}