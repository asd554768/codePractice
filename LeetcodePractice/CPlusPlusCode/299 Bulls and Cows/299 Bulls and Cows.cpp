class Solution {
public:
    string getHint(string secret, string guess) {
        int countA=0;
        int countB=0;
        //string result="";
        unordered_map <char,int> mpS;
        unordered_map <char,int> mpG;
        for(int i=0;i<secret.size();i++){
            if(secret[i]==guess[i]) countA++;
            mpS[secret[i]]++;
            mpG[guess[i]]++;
        }
        for(int i=0;i<guess.size();i++){

            if(mpS.find(guess[i])!=mpS.end()){
                /*if(mpS[guess[i]]>=mpG[guess[i]]){
                    countB+=mpG[guess[i]];
                    mpG.erase(guess[i]);
                }else if(mpS[guess[i]]<mpG[guess[i]]){
                    countB+=mpS[guess[i]];
                    mpG.erase(guess[i]);                    
                }*/
                countB+=min(mpS[guess[i]],mpG[guess[i]]);
                mpS.erase(guess[i]);
            }
        }
        //result=;
        //cout<<countA<<" "<<countB<<endl;
        return to_string(countA)+"A"+to_string(countB-countA)+"B";
    }
};