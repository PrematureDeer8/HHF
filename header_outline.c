#include <stdio.h>

typedef struct Point {
    int x;
    int y;
} Point;


float headerAlgorithm(int num_of_cols, int num_of_rows, int img[][num_of_cols], Point* start){
    Point current;
    current.x = start->x;
    current.y = start->y;
    // lets complete an L shape
    // assuming we start from the top left corner 
    // we have two moves down (positive direction) or right

    // check to see if we can only move right or down (not either)
    // if we cant move down then we must move right
    if(!img[current.y + 1][current.x]){
        
    }
    return 0;
}