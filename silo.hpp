#ifndef SILO_HPP
#define SILO_HPP

#include <string>
#include <vector>
#include <list>
#include <cmath>
#include <limits>
#include <iostream>

// 1. Estructuras de Datos Base
struct Position {
    int aisle, side, x, y, z;

    // Lee el formato sin guiones: "01010010101"
    static Position fromString(const std::string& code) {
        return {
            std::stoi(code.substr(0, 2)),   // Aisle (01)
            std::stoi(code.substr(2, 2)),   // Side  (01)
            std::stoi(code.substr(4, 3)),   // X     (001)
            std::stoi(code.substr(7, 2)),   // Y     (01)
            std::stoi(code.substr(9, 2))    // Z     (01)
        };
    }
};

struct Box {
    std::string fullID;
    std::string destination;
    Position pos;
    bool isReserved = false;
    // Constructor básico
    Box(std::string id, std::string dest) : fullID(id), destination(dest) {}
};

class PalletManager;
class Silo;


// 2. Clase Shuttle (ahora con colas integradas)
class Shuttle {
public:
    int aisle;
    int levelY;
    int currentX;
    double totalBusyTime;

    std::list<Box> pendingInputs;
    std::list<Box> pendingOutputs;

    Shuttle(int a, int y) : aisle(a), levelY(y), currentX(0), totalBusyTime(0.0) {}
    
    // Método para que findBestSlot pueda leer la carga de trabajo
    int getQueueSize() const { 
        return pendingInputs.size() + pendingOutputs.size(); 
    }

    void executeNextCycle(Silo& silo, PalletManager& manager);
};

// 3. Clase Silo
class Silo {
private:
    // Nuestro almacén 5D. Usamos dimensiones +1 para facilitar el mapeo
    Box* grid[5][3][61][9][3]; 

public:
    Silo(); // Constructor para inicializar a nullptr
    
    // Encontrar mejor posicion para dejar la caja
    Position findBestSlot(const Box& newBox, const std::vector<std::vector<Shuttle>>& shuttles);

    // Método para que el shuttle encuentre su próxima caja de salida
    Box* findBestBoxToPick(int aisle, int currentX, int levelY);
    
    // Getter
    Box* getBox(int a, int s, int x, int y, int z) const;

    // Guarda una caja en el grid usando memoria dinámica
    void storeBox(const Box& box);
    
    // Elimina una caja del grid y libera la memoria
    void removeBox(const Position& pos);
    
    // Devuelve todas las cajas actuales para que el PalletManager pueda contarlas
    std::vector<Box*> getAllBoxes() const;
};

#endif // SILO_HPP