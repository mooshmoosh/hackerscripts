#include <stdio.h>
#include <stdlib.h>

typedef struct {
    unsigned char table[8];
    unsigned int inputs[8];
} Expression;

typedef struct {
    Expression * expressions;
    unsigned int size;
} Program;

typedef struct {
    unsigned char * memory;
    unsigned int size;
} MemoryBlock;

#define MEMORY_SIZE 8

MemoryBlock create_memory_block(unsigned int size)
{
    MemoryBlock result;
    result.memory = malloc(sizeof(char) * size / 8);
    result.size = size;
    return result;
}

void delete_memory_block(MemoryBlock block)
{
    free(block.memory);
    block.memory= NULL;
    block.size = 0;
}

Program create_program(unsigned int size)
{
    Program result;
    result.expressions = malloc(sizeof(Expression));
    result.size = size;
    return result;
}

void delete_program(Program program)
{
    free(program.expressions);
    program.expressions = NULL;
    program.size = 0;
}

unsigned int get_bit(const MemoryBlock block, unsigned int location)
{
    return (block.memory[location / 8] >> (location % 8)) & 1UL;
}

void set_bit(MemoryBlock block, unsigned int location, unsigned int bit)
{
    bit &= 1UL;
    unsigned char number = block.memory[location / 8];
    block.memory[location / 8] ^= (-bit ^ number) & (1UL << (location % 8));
}

unsigned int evaluate(const Expression expr, const MemoryBlock block)
{
    unsigned char input = get_bit(block, expr.inputs[0]);
    input = (input << 1) & get_bit(block, expr.inputs[1]);
    input = (input << 1) & get_bit(block, expr.inputs[2]);
    input = (input << 1) & get_bit(block, expr.inputs[3]);
    input = (input << 1) & get_bit(block, expr.inputs[4]);
    input = (input << 1) & get_bit(block, expr.inputs[5]);
    input = (input << 1) & get_bit(block, expr.inputs[6]);
    input = (input << 1) & get_bit(block, expr.inputs[7]);
    return (expr.table[input / 8] >> (input % 8)) & 1;
}

void calculate(const Program prog, unsigned int location, MemoryBlock block)
{
    set_bit(block, location, evaluate(prog.expressions[location], block));
}

void forward_pass(Program prog, MemoryBlock block)
{
    int i;
    for (i = 0; i < prog.size; ++i) {
        calculate(prog, i, block);
    }
}

Expression expression_from_function(unsigned int (*function)(unsigned char), const int inputs[8])
{
    Expression result;
    MemoryBlock table;
    table.memory = &(result.table[0]);
    table.size = 8;
    unsigned int bit;
    unsigned int i;
    unsigned char number;
    for (i=0; i < 256; ++i) {
        bit = function((unsigned char) i);
        number = result.table[i / 8];
        result.table[i / 8] ^= (-bit ^ number) & (1UL << (i % 8));
    }
    result.inputs[0] = inputs[0];
    result.inputs[1] = inputs[1];
    result.inputs[2] = inputs[2];
    result.inputs[3] = inputs[3];
    result.inputs[4] = inputs[4];
    result.inputs[5] = inputs[5];
    result.inputs[6] = inputs[6];
    result.inputs[7] = inputs[7];
    return result;
}

unsigned int and_func(unsigned char input)
{
    return (input >> 6) & (input >> 7) & 1UL;
}

int main()
{
    MemoryBlock block = create_memory_block(16);
    set_bit(block, 0, 1);
    set_bit(block, 1, 1);
    set_bit(block, 2, 1);
    set_bit(block, 3, 1);
    set_bit(block, 4, 1);
    set_bit(block, 5, 1);
    set_bit(block, 6, 1);
    set_bit(block, 7, 1);
    set_bit(block, 8, 1);
    set_bit(block, 9, 0);
    set_bit(block, 10, 0);
    set_bit(block, 11, 1);
    set_bit(block, 12, 1);
    set_bit(block, 13, 0);
    set_bit(block, 14, 1);
    set_bit(block, 15, 0);

    printf("bit 0 is %d\n", get_bit(block, 0));
    printf("bit 1 is %d\n", get_bit(block, 1));
    printf("bit 2 is %d\n", get_bit(block, 2));
    printf("bit 3 is %d\n", get_bit(block, 3));
    printf("bit 4 is %d\n", get_bit(block, 4));
    printf("bit 5 is %d\n", get_bit(block, 5));
    printf("bit 6 is %d\n", get_bit(block, 6));
    printf("bit 7 is %d\n", get_bit(block, 7));
    printf("bit 8 is %d\n", get_bit(block, 8));
    printf("bit 9 is %d\n", get_bit(block, 9));
    printf("bit 10 is %d\n", get_bit(block, 10));
    printf("bit 11 is %d\n", get_bit(block, 11));
    printf("bit 12 is %d\n", get_bit(block, 12));
    printf("bit 13 is %d\n", get_bit(block, 13));
    printf("bit 14 is %d\n", get_bit(block, 14));
    printf("bit 15 is %d\n", get_bit(block, 15));

    unsigned int inputs[8] = { 0, 1, 2, 3, 4, 5, 6, 7};

    Expression and_expr = expression_from_function(and_func, inputs);
    int i;
    for (i=0; i < 8; i++) {
        printf("%u,", and_expr.table[i]);
    }
    printf("\n");

    delete_memory_block(block);
}

