class Solution {
public:
    int uniquePaths(int m, int n) {
        int a,width;
        unsigned long long son=1;
        
        
        a=m+n-2;//長和寬交集處-1和起點減1
        /*
        舉例:一個長寬3*2的矩形方格只需要走3步(3+2-2)
        並且移動只會有兩種選擇往下與往右
        */
        if(m>n) {//檢查誰是長和寬
            //b=m-1;
            width=n-1;
        }else{
            //b=n-1;
            width=m-1;
        } 
        for(int i=1;i<=width;i++){
            
            son=son*(a)/i;
            a--;
        }
        return son;
        
    }
};