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
static int mods=1e9+7;
class Solution {
public:
    
    long long total=0;
    long long result=0;
    void totalSum(TreeNode *root){
        if(!root) return;
        if(root->left){
            total+=root->left->val;
            totalSum(root->left);
        }

        
        if(root->right){
            total+=root->right->val;
            totalSum(root->right);
        }
    }
    int dfsfind(TreeNode* root){
        if(!root) return 0;
        long long leftsum=dfsfind(root->left);
        long long rightsum=dfsfind(root->right);
        result=max(result,(total-leftsum)*leftsum);
        result=max(result,(total-rightsum)*rightsum);
        return (leftsum)+(rightsum)+(root->val);
    }
    int maxProduct(TreeNode* root) {
        
        total+=root->val;
        totalSum(root);
        dfsfind(root);
        //cout<<total<<endl;
        return result%mods;

    }
};