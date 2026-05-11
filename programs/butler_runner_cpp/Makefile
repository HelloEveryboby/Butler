CXX = g++
CXXFLAGS = -O3 -s -I./include -I./include/ixwebsocket
LDFLAGS = -lpthread -lz

SRC = main.cpp include/ixwebsocket/*.cpp
OBJ = butler_music_runner

all: $(OBJ)

$(OBJ): $(SRC)
	$(CXX) $(CXXFLAGS) $^ $(LDFLAGS) -o $@

clean:
	rm -f $(OBJ)

.PHONY: all clean
