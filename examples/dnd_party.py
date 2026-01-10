"""
D&D Party Scenario - Classic adventuring party coordination.

This example demonstrates coordinating a D&D adventuring party with:
- Tank (Fighter) - engages enemies, protects party
- Healer (Cleric) - heals wounded party members
- DPS (Wizard/Rogue) - deals damage
- Support (Bard) - buffs party, debuffs enemies
"""

import asyncio
import random
import sys
import os
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_coordinator import (
    AgentCoordinator,
    AgentRole,
    Task,
    TaskPriority,
    create_task,
    AgentMessage,
    MessageType,
    create_message,
)


class Encounter:
    """Represents a combat encounter."""

    def __init__(
        self,
        name: str,
        enemies: int = 1,
        boss: bool = False,
        difficulty: int = 1,
    ):
        self.name = name
        self.enemies = enemies
        self.boss = boss
        self.difficulty = difficulty
        self.enemy_hp = enemies * (10 if not boss else 50)


class PartyMember:
    """Represents a party member's state."""

    def __init__(self, name: str, role: str, max_hp: int = 20):
        self.name = name
        self.role = role
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.actions_per_round = 1


class DNDPartyScenario:
    """
    D&D Party coordination scenario.

    Creates a classic adventuring party and runs encounters.
    """

    def __init__(self):
        self.coordinator = None
        self.party_members: Dict[str, PartyMember] = {}
        self.party_agents: Dict[str, str] = {}  # agent_id -> member_name
        self.current_encounter: Encounter = None

    async def setup(self) -> AgentCoordinator:
        """Set up the party and coordinator."""
        from agent_coordinator import create_coordinator, CoordinatorConfig

        self.coordinator = create_coordinator(name="adventuring-party")
        await self.coordinator.start()

        # Define roles
        roles = [
            AgentRole(
                name="fighter",
                capabilities=["tank", "melee", "protect", "engage"],
                emoji="⚔️",
            ),
            AgentRole(
                name="cleric",
                capabilities=["heal", "support", "buff", "cure"],
                emoji="🙏",
            ),
            AgentRole(
                name="wizard",
                capabilities=["magic", "aoe", "fireball", "lightning"],
                emoji="🔮",
            ),
            AgentRole(
                name="rogue",
                capabilities=["stealth", "scout", "backstab", "traps"],
                emoji="🗡️",
            ),
        ]

        for role in roles:
            await self.coordinator.register_role(role)

        # Create party members
        self.party_members = {
            "thorin": PartyMember("Thorin Ironforge", "fighter", max_hp=30),
            "elara": PartyMember("Elara Moonwhisper", "cleric", max_hp=18),
            "gandalf": PartyMember("Gandalf Pyrefire", "wizard", max_hp=14),
            "shadow": PartyMember("Shadow", "rogue", max_hp=16),
        }

        # Spawn agents for each party member
        agent_handlers = {
            "fighter": self._fighter_handler,
            "cleric": self._cleric_handler,
            "wizard": self._wizard_handler,
            "rogue": self._rogue_handler,
        }

        for member_name, member in self.party_members.items():
            agent_id = f"{member.role}-{member_name.lower()}"

            def make_task_handler(m=member, h=agent_handlers[member.role]):
                return lambda task: h(m, task)

            await self.coordinator.spawn_agent(
                agent_id=agent_id,
                role=member.role,
                task_handler=make_task_handler(),
                message_handler=self._message_handler,
            )

            self.party_agents[agent_id] = member_name

        print(f"\n⚔️  D&D Party Assembled! ⚔️")
        for member in self.party_members.values():
            print(f"  {member.name} - {member.role.title()} (HP: {member.current_hp}/{member.max_hp})")

        return self.coordinator

    def _fighter_handler(self, member: PartyMember, task: Task) -> dict:
        """Fighter action - engage and protect."""
        action = task.payload.get("action", "attack")

        if action == "protect":
            target = task.payload.get("target", "party")
            return {
                "action": "protect",
                "agent": member.name,
                "target": target,
                "result": f"{member.name} raises their shield, protecting the {target}!",
            }
        elif action == "engage":
            enemies = task.payload.get("enemies", 1)
            damage = random.randint(8, 15) * enemies
            return {
                "action": "attack",
                "agent": member.name,
                "damage": damage,
                "result": f"{member.name} charges into battle, dealing {damage} damage!",
            }

        return {"action": "ready", "agent": member.name}

    def _cleric_handler(self, member: PartyMember, task: Task) -> dict:
        """Cleric action - heal and support."""
        action = task.payload.get("action", "heal")

        if action == "heal":
            target = task.payload.get("target", member.name)
            heal_amount = random.randint(8, 12)
            return {
                "action": "heal",
                "agent": member.name,
                "target": target,
                "amount": heal_amount,
                "result": f"{member.name} prays and heals {target} for {heal_amount} HP!",
            }
        elif action == "buff":
            return {
                "action": "buff",
                "agent": member.name,
                "result": f"{member.name} casts Bless on the party!",
            }

        return {"action": "ready", "agent": member.name}

    def _wizard_handler(self, member: PartyMember, task: Task) -> dict:
        """Wizard action - AOE magic damage."""
        action = task.payload.get("action", "magic")

        if action == "aoe":
            enemies = task.payload.get("enemies", 1)
            damage = random.randint(20, 30)
            total = damage * enemies
            return {
                "action": "aoe",
                "agent": member.name,
                "spell": task.payload.get("spell", "Fireball"),
                "damage": total,
                "result": f"{member.name} casts Fireball! {total} total damage!",
            }
        elif action == "magic":
            damage = random.randint(15, 25)
            return {
                "action": "magic",
                "agent": member.name,
                "damage": damage,
                "result": f"{member.name} casts Magic Missile for {damage} damage!",
            }

        return {"action": "ready", "agent": member.name}

    def _rogue_handler(self, member: PartyMember, task: Task) -> dict:
        """Rogue action - stealth and backstab."""
        action = task.payload.get("action", "attack")

        if action == "scout":
            return {
                "action": "scout",
                "agent": member.name,
                "result": f"{member.name} slips into the shadows to scout ahead...",
            }
        elif action == "backstab":
            damage = random.randint(12, 20) * 2  # Sneak attack!
            return {
                "action": "backstab",
                "agent": member.name,
                "damage": damage,
                "result": f"{member.name} strikes from stealth! {damage} critical damage!",
            }
        elif action == "attack":
            damage = random.randint(8, 12)
            return {
                "action": "attack",
                "agent": member.name,
                "damage": damage,
                "result": f"{member.name} strikes with their daggers for {damage} damage!",
            }

        return {"action": "ready", "agent": member.name}

    def _message_handler(self, message: AgentMessage) -> None:
        """Handle inter-agent messages."""
        print(f"  [Message] {message.from_agent} -> {message.to_agent}: {message.message_type.value}")

    async def run_encounter(self, encounter: Encounter) -> dict:
        """Run a combat encounter."""
        print(f"\n{'='*50}")
        print(f"ENCOUNTER: {encounter.name}")
        print(f"Enemies: {encounter.enemies} {'(BOSS!)' if encounter.boss else ''}")
        print(f"{'='*50}\n")

        self.current_encounter = encounter
        results = {"rounds": 0, "total_damage": 0, "actions": []}

        # Combat loop
        round_num = 1
        while encounter.enemy_hp > 0:
            print(f"\n--- Round {round_num} ---")

            # Fighter engages first
            fighter_task = create_task(
                description="Engage enemies",
                capabilities=["tank", "engage"],
                payload={"action": "engage", "enemies": encounter.enemies},
            )
            fighter_result = await self.coordinator.submit_task(fighter_task, wait_for_completion=True)
            if fighter_result and fighter_result.success:
                print(f"  {fighter_result.result.get('result', 'Fighter acts')}")
                encounter.enemy_hp -= fighter_result.result.get("damage", 0)
                results["total_damage"] += fighter_result.result.get("damage", 0)
                results["actions"].append(fighter_result.result)

            if encounter.enemy_hp <= 0:
                break

            # Wizard casts AOE if multiple enemies
            if encounter.enemies > 1:
                wizard_task = create_task(
                    description="Cast AOE spell",
                    capabilities=["magic", "aoe"],
                    payload={"action": "aoe", "enemies": encounter.enemies, "spell": "Fireball"},
                )
                wizard_result = await self.coordinator.submit_task(wizard_task, wait_for_completion=True)
                if wizard_result and wizard_result.success:
                    print(f"  {wizard_result.result.get('result', 'Wizard acts')}")
                    encounter.enemy_hp -= wizard_result.result.get("damage", 0)
                    results["total_damage"] += wizard_result.result.get("damage", 0)
                    results["actions"].append(wizard_result.result)

                if encounter.enemy_hp <= 0:
                    break

            # Rogue backstabs or attacks
            rogue_task = create_task(
                description="Attack enemy",
                capabilities=["stealth", "attack"],
                payload={"action": "backstab" if round_num == 1 else "attack"},
            )
            rogue_result = await self.coordinator.submit_task(rogue_task, wait_for_completion=True)
            if rogue_result and rogue_result.success:
                print(f"  {rogue_result.result.get('result', 'Rogue acts')}")
                encounter.enemy_hp -= rogue_result.result.get("damage", 0)
                results["total_damage"] += rogue_result.result.get("damage", 0)
                results["actions"].append(rogue_result.result)

            if encounter.enemy_hp <= 0:
                break

            # Enemy attacks back!
            damage_taken = random.randint(5, 15) * encounter.enemies
            print(f"  Enemies strike back! Party takes {damage_taken} damage!")

            # Cleric heals
            cleric_task = create_task(
                description="Heal party",
                capabilities=["heal"],
                payload={"action": "heal", "target": "party"},
            )
            cleric_result = await self.coordinator.submit_task(cleric_task, wait_for_completion=True)
            if cleric_result and cleric_result.success:
                print(f"  {cleric_result.result.get('result', 'Cleric acts')}")
                results["actions"].append(cleric_result.result)

            round_num += 1
            results["rounds"] = round_num

            # Safety break
            if round_num > 10:
                print("\nThe party retreats!")
                break

        print(f"\n{'='*50}")
        if encounter.enemy_hp <= 0:
            print(f"VICTORY! {encounter.name} defeated in {round_num} rounds!")
        else:
            print(f"The party was overwhelmed...")
        print(f"{'='*50}")

        return results

    async def cleanup(self) -> None:
        """Clean up after the scenario."""
        if self.coordinator:
            await self.coordinator.shutdown()


async def main():
    """Run the D&D Party scenario."""
    scenario = DNDPartyScenario()

    try:
        await scenario.setup()

        # Run encounters
        encounters = [
            Encounter("Goblin Ambush", enemies=3, boss=False),
            Encounter("Orc Patrol", enemies=2, boss=False),
            Encounter("Dragon!", enemies=1, boss=True, difficulty=5),
        ]

        for encounter in encounters:
            await scenario.run_encounter(encounter)

        # Show final status
        print("\n" + "="*50)
        print("Adventure Complete! Final Party Status:")
        print("="*50)
        for member in scenario.party_members.values():
            status = "Healthy" if member.current_hp > member.max_hp / 2 else "Wounded"
            print(f"  {member.name}: {status} ({member.current_hp}/{member.max_hp} HP)")

    finally:
        await scenario.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
