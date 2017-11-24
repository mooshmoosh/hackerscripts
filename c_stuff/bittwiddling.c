#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

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

unsigned int get_bit_in_char(unsigned char bits, unsigned int location)
{
    return (bits >> location) & 1UL;
}

unsigned int get_bit(const MemoryBlock block, unsigned int location)
{
    return get_bit_in_char(block.memory[location / 8], location % 8);
}

void set_bit_in_char(unsigned char * bits, unsigned int location, unsigned int bit)
{
    bit &= 1UL;
    unsigned char number = *bits;
    *bits ^= (-bit ^ number) & (1UL << location);
}

void set_bit(MemoryBlock block, unsigned int location, unsigned int bit)
{
    set_bit_in_char(&(block.memory[location / 8]), location % 8, bit);
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
    unsigned int bit;
    unsigned int i;
    unsigned int j;
    unsigned char number;
    for (i=0; i < 256; ++i) {
        bit = function((unsigned char) (i));
        printf("and of %x = %x\n", i, bit);
        set_bit_in_char(&(result.table[(unsigned int) i / 8]), (unsigned int) i % 8, bit);
    }

    for (i = 0; i < 8; i++) {
        printf("%x ", result.table[i]);
    }
    printf("\n");
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
    return ((input >> 6) & (input >> 7) & 1UL);
}

int main()
{
    unsigned char bits;
    int i;
    bits = 2;
    set_bit_in_char(&bits, 0, 1);
    assert(bits == 3);
    set_bit_in_char(&bits, 1, 0);
    assert(bits == 1);
    set_bit_in_char(&bits, 2, 1);
    assert(bits == 5);

    bits = 9;
    assert(get_bit_in_char(bits, 0) == 1);
    assert(get_bit_in_char(bits, 1) == 0);
    assert(get_bit_in_char(bits, 2) == 0);
    assert(get_bit_in_char(bits, 3) == 1);
    unsigned int inputs[8] = {0, 1, 2, 3, 4, 5, 6, 7};
    Expression expr = expression_from_function(and_func, inputs);

}

