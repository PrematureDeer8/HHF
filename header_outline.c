#include <stdio.h>
#include <stdbool.h>
#include <math.h>

#define trail 257

typedef struct Point {
    int x;
    int y;
} Point;


float headerAlgorithm(int num_of_cols, int num_of_rows, int img[][num_of_cols], Point* start, float helper_line[]){
    // helper_line -> int (start x), int (stop x), int (m), int (b)
    int avg_y = 0;
    float dst_vect[2];
    int divot_vect[2] = {0, 0};
    int bias_factor = 2;
    float obj_y;
    float obj_x = helper_line[0];
    float m = helper_line[2];
    float b = helper_line[3];
    float distance;
    int count = 0;
    Point current;
    current.x = start->x;
    current.y = start->y;

    // printf("X: %d\n", current.x);
    // printf("Y: %d\n", current.y);
    // printf("Xs: %.2f\n", helper_line[0]);
    // printf("Xe: %.2f\n", helper_line[1]);
    // printf("m: %.2f\n", helper_line[2]);
    // printf("b: %.2f\n", helper_line[3]);
    
    printf("X: %d Y: %d\n",current.x, current.y);
    while(true){

        // find the distance between the the helper line start point 
        // and the starting point of the table
        obj_y = obj_x * m + b;
        dst_vect[0] = fabsf(obj_x - current.x);
        dst_vect[1] = fabsf(obj_y - current.y);
        distance = sqrt(pow(dst_vect[0],2) + pow(dst_vect[1],2));
        // the x distance is greater than the y 
        // try stepping to the right if the pixel is still black
        if(dst_vect[0] > dst_vect[1] && img[current.y][current.x + 1] == 0){
            // try to step in the x direction (if possible)
            current.x++;
            obj_x++;
            count++;
            avg_y += current.y;
        }else if(dst_vect[1] > dst_vect[0] && img[current.y + 1][current.x] == 0)
        {
            current.y++;
            obj_x++;
        }else if(img[current.y][current.x + 1] == 0){
            current.x++;
            count++;
            avg_y += current.y;

        }else if(img[current.y + 1][current.x] == 0){
            current.y++;
        // both down and right are white
        }else{
            // we must move either up or left (or a combination of both)
            // look at all the surrounding pixels and calculate their 
            // gradient
            // scale factor on the down and right is increased because of 
            for(int i = 0; i < 8; i++){
                switch(i){
                    case 0: 
                        divot_vect[1] -= (255 - img[current.y - 1][current.x]) / 255;
                        break;
                    case 1:
                        divot_vect[0] += bias_factor * (255 - img[current.y - 1][current.x + 1]) / 255;
                        divot_vect[1] -= (255 - img[current.y - 1][current.x + 1]) / 255;
                        break;
                    case 2:
                        divot_vect[0] += bias_factor * (255 - img[current.y][current.x + 1]) / 255;
                        break;
                    case 3:
                        divot_vect[0] += bias_factor * (255 - img[current.y + 1][current.x + 1]) / 255;
                        divot_vect[1] += bias_factor * (255 - img[current.y + 1][current.x + 1]) / 255;
                        break;
                    case 4:
                        divot_vect[1] += bias_factor * (255 - img[current.y + 1][current.x]) / 255;
                        break;
                    case 5:
                        divot_vect[0] -= (255 - img[current.y + 1][current.x - 1]) / 255;
                        divot_vect[1] += bias_factor * (255 - img[current.y + 1][current.x - 1]) / 255;
                        break;
                    case 6:
                        divot_vect[0] -= (255 - img[current.y][current.x - 1]) / 255;
                        break;
                    case 7:
                        divot_vect[0] -= (255 - img[current.y][current.x - 1]) / 255;
                        divot_vect[1] -= (255 - img[current.y][current.x - 1]) / 255;
                        break;
                }
            }
            if(divot_vect[0] > 0){
                current.x++;
                count++;
                avg_y += current.y;
            }else{
                current.x--;
            }
            if(divot_vect[1] > 0){
                current.y++;
            }else{
                current.y--;
            }

        }
        if(obj_x >= helper_line[1]){
            obj_x = helper_line[1];
            break;
        }
        // if we our going off the deep end then just stop
        if(count >= 500 && count >= 500){
            break;
        }
        // discourage going back from the tile that you came from
        img[current.y][current.x] = trail;

        // printf("X: %d Y: %d  Distance : %.2f\n",current.x, current.y, distance);
    }
    // printf("X: %d Y: %d \n", current.x, current.y);
    avg_y /= count;
    return avg_y;
}