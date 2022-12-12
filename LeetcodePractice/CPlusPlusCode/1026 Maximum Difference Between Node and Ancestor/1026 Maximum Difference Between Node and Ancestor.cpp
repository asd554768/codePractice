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
    int ans=INT_MIN; 
    void helper(vector<int> ancestor,TreeNode* root){
        if(!root->left && !root->right){
            sort(ancestor.begin(),ancestor.end());
            int maxs=max(ancestor[0],ancestor[ancestor.size()-1])-min(ancestor[0],ancestor[ancestor.size()-1]);
            if(maxs>ans) ans=maxs;
            return;
        }
        if(root->left){
            ancestor.push_back(root->left->val);
            helper(ancestor,root->left);
            ancestor.pop_back();
        }
        if(root->right){
            ancestor.push_back(root->right->val);
            helper(ancestor,root->right);
        }
    }
    int maxAncestorDiff(TreeNode* root) {
        vector <int> ancestor;
        ancestor.push_back(root->val);
        helper(ancestor,root);
        return ans;

    }
};