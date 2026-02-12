from __future__ import annotations

from collections import defaultdict

RAW_BLUEPRINT_PLAN = """10MN Afterburner II\t1296\n1200mm Artillery Cannon II\t864\n150mm Railgun II\t2593\n250mm Light Artillery Cannon II\t2593\n350mm Railgun II\t864\n650mm Artillery Cannon II\t1296\nAbsolution\t20\nAnathema\t53\nAres\t53\nBustard\t25\nBustard\t25\nBuzzard\t53\nClaw\t53\nClaymore\t20\nCo-Processor II\t2593\nCrane\t25\nCrow\t53\nCrusader\t53\nCrusader\t53\nDamage Control II\t2593\nDeimos\t25\nDual 650mm Repeating Cannon II\t864\nDual Light Beam Laser II\t2593\nEagle\t25\nElectron Blaster Cannon II\t864\nEnyo\t53\nEris\t33\nFlycatcher\t33\nGleam L\t1684\nGravimetric ECM II\t1296\nGuardian\t25\nGyrostabilizer II\t2593\nHail M\t3160000\nHammerhead II\t2022\nHammerhead II\t2022\nHarpy\t53\nHawk\t53\nHeat Sink II\t2593\nHeavy Beam Laser II\t1296\nHeavy Electron Blaster II\t1296\nHelios\t53\nHeretic\t33\nHound\t53\nInferno Precision Cruise Missile\t2105000\nInferno Rage Torpedo\t2105000\nIon Blaster Cannon II\t864\nIshkur\t53\nJaguar\t53\nKinetic Energized Membrane II\t2593\nKinetic Shield Amplifier II\t1296\nLachesis\t25\nLarge Shield Booster II\t1296\nLayered Energized Membrane II\t2593\nLight Electron Blaster II\t2593\nMagnetic Field Stabilizer II\t2593\nMalediction\t53\nMastodon\t25\nMedium Armor Repairer II\t1296\nMedium Cap Battery II\t1296\nMedium Capacitor Booster II\t1296\nMedium Energy Nosferatu II\t1296\nMedium Proton Smartbomb II\t1296\nMedium Shield Booster II\t2593\nMedium Shield Extender II\t2593\nMega Beam Laser II\t864\nMiner II\t2593\nMjolnir Fury Cruise Missile\t2105000\nMobile Small Warp Disruptor II\t404\nMobile Small Warp Disruptor II\t404\nMuninn\t25\nNemesis\t53\nNighthawk\t20\nNova Javelin Torpedo\t2105000\nNova Javelin Torpedo\t2105000\nOgre II\t1348\nPower Diagnostic System II\t2593\nPraetor II\t1348\nProrator\t25\nProwler\t25\nPurifier\t53\nPurifier\t53\nRapid Light Missile Launcher II\t1296\nRaptor\t53\nReactor Control Unit II\t2593\nRemote Sensor Dampener II\t1296\nRemote Tracking Computer II\t1296\nRetribution\t53\nScourge Fury Cruise Missile\t2105000\nScourge Fury Light Missile\t6320000\nScourge Precision Cruise Missile\t2105000\nScourge Precision Light Missile\t6320000\nScourge Rage Torpedo\t2105000\nSensor Booster II\t1296\nShield Boost Amplifier II\t1296\nSignal Amplifier II\t2593\nSignal Amplifier II\t2593\nSignal Amplifier II\t2593\nSignal Amplifier II\t2593\nSignal Amplifier II\t2593\nSkiff\t25\nSleipnir\t20\nSmall Cap Battery II\t2593\nSmall Capacitor Booster II\t2593\nSmall EMP Smartbomb II\t2593\nSmall Focused Beam Laser II\t2593\nSmall Focused Pulse Laser II\t2593\nSmall Shield Booster II\t2593\nSmall Shield Extender II\t2593\nSpike L\t2105000\nSpike S\t6320000\nSpike S\t6320000\nStiletto\t53\nTaranis\t53\nThermal Coating II\t2593\nThermal Shield Hardener II\t1296\nTracking Computer II\t1296\nTracking Disruptor II\t1296\nTracking Enhancer II\t2593\nTracking Enhancer II\t2593\nVagabond\t25\nVengeance\t53\nViator\t25\nVulture\t20\nWasp II\t1348\nWolf\t53\nZealot\t25\nCoherent Asteroid Mining Crystal Type A II\t12642\nCoherent Asteroid Mining Crystal Type A II\t12642\nComplex Asteroid Mining Crystal Type A II\t12642\nComplex Asteroid Mining Crystal Type A II\t12642\nComplex Asteroid Mining Crystal Type A II\t12642\nSimple Asteroid Mining Crystal Type A II\t12642\nVariegated Asteroid Mining Crystal Type A II\t12642"""


def parse_build_plan(raw_plan: str) -> dict[str, int]:
    totals: defaultdict[str, int] = defaultdict(int)
    cleaned = raw_plan.replace("\\n", "\n")
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name, quantity = line.rsplit("\t", 1)
        totals[name.strip()] += int(quantity)
    return dict(totals)


STATIC_BUILD_QUANTITIES = parse_build_plan(RAW_BLUEPRINT_PLAN)
