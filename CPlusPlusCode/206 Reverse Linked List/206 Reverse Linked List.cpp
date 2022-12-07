/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    ListNode* reverseList(ListNode* head) {
        if(!head || !head->next) return head;

        ListNode* front=head;
        ListNode* rear=head->next;
        ListNode* temp;
        front->next=nullptr;
        while(rear){
            temp=rear;
            rear=rear->next;
            temp->next=front;
            front=temp;
        }
        return front;
       
        
    }
};