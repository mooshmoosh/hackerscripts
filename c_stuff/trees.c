
#define TREE_DEPTH (5)
#define FOREST_SIZE (10)
#define DECISION_WIDTH (5)
#define TREE_SIZE (1 << TREE_DEPTH)

struct TreeNode
{
    double threshold;
    unsigned int coordinates[DECISION_WIDTH];
    double weights[DECISION_WIDTH];
    int category;
}

struct Tree
{
    struct TreeNode[TREE_SIZE];
}

struct Forest
{
    struct Tree[FOREST_SIZE];
}

unsigned int goLeft(unsigned int node_index)
{
    return node_index + 1
}

unsigned int goRight(unsigned int node_index)
{
    return node_index
}

/*
1 2
3 4

1 2 3
  4
5 6 7
  8

1 2  3  4
  5  6  7
     8
9 10 11 12
  13 14 15
     16
