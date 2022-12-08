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
    void helper(vector<string>& vc,TreeNode* root){
        if(!root->left && !root->right){
            vc.back()+=to_string(root->val);
            return;
        }
        if(root->left && !root->right){
            vc.back()+=to_string(root->val);
            vc.back()+="->";
            
            helper(vc,root->left);
        }
        if(!root->left && root->right){
            vc.back()+=to_string(root->val);
            vc.back()+="->";
            
            helper(vc,root->right);
        } 
        if(root->left && root->right){
            vc.back()+=to_string(root->val);
            vc.back()+="->";
            string right=vc.back();

            helper(vc,root->left);
            
            vc.push_back(right);
            helper(vc,root->right);
        }
        return;       
    }
    vector<string> binaryTreePaths(TreeNode* root) {
        vector<string> vc(1,"");
        helper(vc,root);
        //cout<<vc[0]<<endl;
        return vc;
    }
};