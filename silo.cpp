#include "silo.hpp"

// Parámetros de la heurística
const double W_X = 1.0; // Peso que penaliza a cuanta distancia la ponemos
const double W_Q = 50.0; // Penalizamos mucho la saturación del shuttle
const double W_A = 5.0; // Damos un gran bonus por juntar destinos
const double W_Z = 0.5; // A cuanta altura o ponemos
const double W_F = 15; // Peso de penalización por alta rotación

// Constructor del Silo
Silo::Silo() {
    for(int a=0; a<5; ++a)
        for(int s=0; s<3; ++s)
            for(int x=0; x<61; ++x)
                for(int y=0; y<9; ++y)
                    for(int z=0; z<3; ++z)
                        grid[a][s][x][y][z] = nullptr;
}


void Silo::loadHistory(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "[AVISO] No se encontró el historico: " << filename << "\n";
        return;
    }

    std::string dest;
    double maxFreq = 0.0;
    std::map<std::string, double> rawCounts;
    
    // Saltamos cabecera
    std::getline(file, dest); 
    
    // Contamos apariciones
    while (std::getline(file, dest)) {
        if (!dest.empty() && dest.back() == '\r') dest.pop_back();
        if (dest.empty()) continue;
        
        rawCounts[dest]++;
        if (rawCounts[dest] > maxFreq) maxFreq = rawCounts[dest];
    }
    
    // Normalizamos la frecuencia de 0.0 (raro) a 1.0 (súper popular)
    for (const auto& pair : rawCounts) {
        demandFrequencies[pair.first] = pair.second / maxFreq;
    }
    //std::cout << "[INFO] Inteligencia ABC: Historico cargado con " 
              //<< demandFrequencies.size() << " destinos mapeados.\n";
}

// Implementación del método de búsqueda
Position Silo::findBestSlot(const Box& newBox, const std::vector<std::vector<Shuttle>>& shuttles) {
    Position bestPos = {-1, -1, -1, -1, -1};
    double minCost = std::numeric_limits<double>::max();

    // Iteramos por los 4 PASILLOS
    for(int a = 1; a <= 4; ++a) {
        
        // Iteramos por los 8 NIVELES Y
        for(int y = 1; y <= 8; ++y) {
            
            // Consultamos la carga del shuttle específico de este pasillo y nivel
            int shuttleQueueSize = shuttles[a-1][y-1].getQueueSize(); 
            
            // Si este shuttle ya está muy saturado (ej. tiene > 5 tareas), 
            // podemos saltarnos todo este nivel para ahorrar tiempo de cálculo y forzar balanceo.
            if (shuttleQueueSize > 5) continue; 

            // Iteramos por los 2 LADOS
            for(int s = 1; s <= 2; ++s) {
                // Iteramos por la profundidad X
                for(int x = 1; x <= 60; ++x) {
                    // Iteramos por el fondo Z
                    for(int z = 1; z <= 2; ++z) {
                        
                        // Si el hueco está ocupado, pasamos al siguiente
                        if (grid[a][s][x][y][z] != nullptr) continue;

                        // Calcular Bonus de Afinidad (¿Hay cajas del mismo destino cerca?)
                        // Ahora miramos en el mismo pasillo, mismo lado, misma altura, posición anterior en X
                        double affinityBonus = 0.0;
                        if (x > 1 && grid[a][s][x-1][y][z] != nullptr && 
                            grid[a][s][x-1][y][z]->destination == newBox.destination) {
                            affinityBonus += 1.0;
                        }

                        // Calcular si es un destino de alta rotacion
                        double itemDemand = 0.0;
                        if (useABCAnalysis && demandFrequencies.count(newBox.destination)) {
                            itemDemand = demandFrequencies[newBox.destination];
                        }

                        // LA ECUACIÓN MAESTRA
                        // W_X penaliza alejar la caja.
                        // W_Q penaliza darle la caja a un shuttle que ya tiene mucho trabajo.
                        // W_A premia ponerla cerca de cajas que van al mismo sitio.
                        // W_Z penaliza ponerla en el fondo (Z=2) si Z=1 está libre.
                        // W_F Si la demanda es alta, cada paso en X cuesta muchísimo más.
                        // Esto obliga a las cajas A (Top Ventas) a pelearse por las primeras posiciones X.
                        double cost = 
                                    (W_X * x) 
                                    + (W_Q * shuttleQueueSize) 
                                    - (W_A * affinityBonus) 
                                    + (W_Z * z) 
                                    + (W_F * itemDemand * x);

                        if (cost < minCost) {
                            minCost = cost;
                            bestPos = {a, s, x, y, z};
                        }
                    }
                }
            }
        }
    }
    return bestPos;
}

Box* Silo::findBestBoxToPick(int aisle, int currentX, int levelY) {
    Box* bestBox = nullptr;
    int minDistance = 9999;

    // Iteramos por los DOS LADOS (1 y 2)
    for (int s = 1; s <= 2; ++s) {

        for (int x = 1; x <= 60; ++x) {
            for (int z = 1; z <= 2; ++z) {
                Box* candidateBox = grid[aisle][s][x][levelY][z]; 
                
                // Si hay caja Y además ha sido reservada por el PalletManager
                if (candidateBox != nullptr && candidateBox->isReserved) {
                    int distance = std::abs(x - currentX);
                    if (distance < minDistance) {
                        minDistance = distance;
                        bestBox = candidateBox;
                    }
                }
            }
        }
    }
    return bestBox;
}

// Implementación de getBox (Búsqueda segura con límites)

Box* Silo::getBox(int a, int s, int x, int y, int z) const {
    // Protección para no salirnos de los límites de la matriz
    if(a > 0 && a < 5 && s > 0 && s < 3 && x > 0 && x < 61 && y > 0 && y < 9 && z > 0 && z < 3) {
        return grid[a][s][x][y][z];
    }
    return nullptr;
}


// Implementación de storeBox (Guardar en el Silo)

void Silo::storeBox(const Box& box) {
    int a = box.pos.aisle;
    int s = box.pos.side;
    int x = box.pos.x;
    int y = box.pos.y;
    int z = box.pos.z;
    
    if(a > 0 && a < 5 && s > 0 && s < 3 && x > 0 && x < 61 && y > 0 && y < 9 && z > 0 && z < 3) {
        if (grid[a][s][x][y][z] == nullptr) {
            // Usamos 'new' para crear una copia de la caja en el heap
            grid[a][s][x][y][z] = new Box(box); 
        } else {
            // Para debug: esto saltaría si el findBestSlot dio una posición ocupada
            std::cerr << "Error: Intentando guardar en un hueco ocupado.\n";
        }
    }
}

// Implementación de removeBox (Sacar del Silo)

void Silo::removeBox(const Position& pos) {
    int a = pos.aisle;
    int s = pos.side;
    int x = pos.x;
    int y = pos.y;
    int z = pos.z;
    
    if(a > 0 && a < 5 && s > 0 && s < 3 && x > 0 && x < 61 && y > 0 && y < 9 && z > 0 && z < 3) {
        if (grid[a][s][x][y][z] != nullptr) {
            // Usamos 'delete' para evitar fugas de memoria (memory leaks)
            delete grid[a][s][x][y][z]; 
            grid[a][s][x][y][z] = nullptr; // Lo volvemos a poner vacío
        }
    }
}


// Implementación de getAllBoxes 

std::vector<Box*> Silo::getAllBoxes() const {
    std::vector<Box*> allBoxes;
    // Iteramos por todo el almacén válido
    for(int a = 1; a <= 4; ++a) {
        for(int s = 1; s <= 2; ++s) {
            for(int x = 1; x <= 60; ++x) {
                for(int y = 1; y <= 8; ++y) {
                    for(int z = 1; z <= 2; ++z) {
                        if(grid[a][s][x][y][z] != nullptr) {
                            allBoxes.push_back(grid[a][s][x][y][z]);
                        }
                    }
                }
            }
        }
    }
    return allBoxes;
}

void Silo::setABCStatus(bool status) {
    useABCAnalysis = status;
    if (status) {
        std::cout << "[SISTEMA] Algoritmo Predictivo ABC: ACTIVADO\n";
    } else {
        std::cout << "[SISTEMA] Algoritmo Predictivo ABC: DESACTIVADO (Modo Estándar)\n";
    }
}