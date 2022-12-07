class Solution {
public:
    int sum=0;
    int rangeSumBST(TreeNode* root, int low, int high) {
        if(!root) return sum;
        if(root->val>low && root->val<high){
            sum+=root->val;
        }
        int left=rangeSumBST(root->left,low,high);
        int right=rangeSumBST(root->right,low,high);
        return sum+low+high;
    }
};