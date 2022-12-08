/**
 * Definition for a binary tree node.
 * struct TreeNode {
 *     int val;
 *     TreeNode *left;
 *     TreeNode *right;
 *     TreeNode() : val(0), left(nullptr), right(nullptr) {}
 *     TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
 *     TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}
 * };
 */
class Solution {
public:
    void helper(vector<int>& vc,TreeNode* root){
        if((!root->left) && (!root->right)){
            vc.push_back(root->val);
            return;
        }
        if(root->left){
            helper(vc,root->left);
        }
        if(root->right){
            helper(vc,root->right);
        }
    }
    bool leafSimilar(TreeNode* root1, TreeNode* root2) {
        vector <int> vc1;
        vector <int> vc2;
        helper(vc1,root1);
        helper(vc2,root2);
        if(vc1.size()!=vc2.size()) return false;
        for(int i=0;i<vc1.size();i++){
            if(vc1[i]!=vc2[i]) return false;
        }
        return true;
    }
};