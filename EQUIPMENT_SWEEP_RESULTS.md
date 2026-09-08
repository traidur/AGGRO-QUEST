# Equipment Equilibrium Sweep Results (Tier 1)

The simulator ran 90 hands across 6 Tier 1 mobs to find the **"Crack Point"** for each class—the starting HP at which they can no longer guarantee a 100% win rate. 

We ran three profiles:
1. **Baseline:** Naked.
2. **Early Tier 1:** Only uses Level 1 materials. `Honed` (+1/+2 DMG) and `Reinforced` (+2/+3/+4 Block).
3. **Advanced Tier 1:** Requires Level 2 materials. `Sunder` (DoT), `Persistent` (Carryover Block), and `Elusive` (Evade).

## The Results

### 🛡️ Heavy Armor (Paladin & Warrior)
**Paladin Crack Points:**
*   Baseline: HP 6
*   **Early T1 (Reinforced): HP 3** *(Massive improvement)*
*   Advanced T1 (Persistent): HP 5

**Warrior Crack Points:**
*   Baseline: HP 7
*   **Early T1 (Reinforced): HP 4** *(Massive improvement)*
*   Advanced T1 (Persistent): HP 7

**The Takeaway:** The +4 Block from Heavy `Reinforced` armor is incredibly strong, pushing their survival floor down by 3 full HP. But crucially, **it does not make them invincible**. A Paladin entering a fight at 2 HP with Heavy Reinforced Plate will still die to a bad hand. 
Interestingly, `Persistent` (Advanced T1) doesn't help their absolute worst-case survival floor, because if you are dying at low HP, you likely didn't have any *excess* block to carry over anyway!

### 🧙‍♂️ Light Armor (Wizard)
**Wizard Crack Points:**
*   Baseline: HP 6
*   Early T1 (Reinforced): HP 6 *(No floor improvement)*
*   **Advanced T1 (Elusive): HP 4** *(Massive improvement)*

**The Takeaway:** A beautiful inversion! The `Reinforced` stat-bump (+2 Block for Light Armor) is too weak to save a Wizard in a worst-case scenario. However, once a Wizard harvests Level 2 materials to craft `Elusive` (evade one melee attack), their survival floor plummets from 6 to 4! 

### 🗡️ Medium Armor (Rogue)
**Rogue Crack Points:**
*   Baseline: HP 7
*   Early T1 (Reinforced): HP 5
*   Advanced T1 (Elusive): HP 5

**The Takeaway:** Medium armor sits perfectly in the middle. The +3 Block from `Reinforced` and the evade from `Elusive` provide the exact same mathematical safety net (both drop the crack point by 2 HP). 

## Final Conclusion
The weight-scaling is a massive success. The Heavy classes get immediate, reliable survival from Level 1 materials, while the Squishy classes are heavily incentivized to survive long enough to harvest Level 2 materials to unlock their powerful evasion mechanics. And most importantly, nobody achieved infinite immortality.
