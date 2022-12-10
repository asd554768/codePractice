/*
// Definition for a Node.
class Node {
public:
    int val;
    vector<Node*> children;

    Node() {}

    Node(int _val) {
        val = _val;
    }

    Node(int _val, vector<Node*> _children) {
        val = _val;
        children = _children;
    }
};
*/

class Solution {
public:
    vector<int> result;
    void helper(Node* root){
        if(!root) return;
        result.push_back(root->val);
        for(int i=0;i<root->children.size();i++){
            helper(root->children[i]);
        }
    }
    vector<int> preorder(Node* root) {
        //cout<<root->children[0]->val<<endl;
        helper(root);
        return result;
    }
};