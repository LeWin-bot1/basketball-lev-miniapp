"""
WebSocket модуль для real-time обновлений турнирной таблицы.

Позволяет клиентам подписываться на обновления турниров в реальном времени.
"""

import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from .database import get_solo_tournament_leaderboard, get_team_tournament_leaderboard


class ConnectionManager:
    """
    Менеджер WebSocket соединений.
    
    Управляет подключениями клиентов и рассылкой обновлений.
    """
    
    def __init__(self):
        # Активные соединения: channel_name -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "solo_tournament": set(),
            "team_tournament": set(),
            "leaderboard": set(),
        }
        self._update_task: asyncio.Task = None
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Подключить клиента к каналу"""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Отключить клиента от канала"""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
    
    async def broadcast(self, channel: str, message: dict):
        """Отправить сообщение всем подключённым клиентам канала"""
        if channel not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Удаляем отключённые соединения
        for conn in disconnected:
            self.active_connections[channel].discard(conn)
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Отправить сообщение конкретному клиенту"""
        try:
            await websocket.send_json(message)
        except Exception:
            pass
    
    def get_connection_count(self, channel: str) -> int:
        """Получить количество подключений к каналу"""
        return len(self.active_connections.get(channel, set()))


# Глобальный менеджер соединений
manager = ConnectionManager()


async def periodic_tournament_update():
    """
    Периодически отправляет обновления турнирной таблицы.
    
    Запускается в фоне и обновляет данные каждые 30 секунд.
    """
    while True:
        try:
            # Обновляем одиночный турнир
            if manager.get_connection_count("solo_tournament") > 0:
                solo_data, total = get_solo_tournament_leaderboard(50)
                await manager.broadcast("solo_tournament", {
                    "type": "tournament_update",
                    "tournament": "solo",
                    "data": {
                        "players": solo_data,
                        "total_participants": total,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                })
            
            # Обновляем командный турнир
            if manager.get_connection_count("team_tournament") > 0:
                team_data, total = get_team_tournament_leaderboard(30)
                await manager.broadcast("team_tournament", {
                    "type": "tournament_update",
                    "tournament": "team",
                    "data": {
                        "teams": team_data,
                        "total_teams": total,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                })
            
            # Ждём 30 секунд перед следующим обновлением
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in periodic update: {e}")
            await asyncio.sleep(5)


async def handle_tournament_websocket(websocket: WebSocket, tournament_type: str):
    """
    Обработчик WebSocket соединения для турнира.
    
    Args:
        websocket: WebSocket соединение
        tournament_type: Тип турнира ("solo" или "team")
    """
    channel = f"{tournament_type}_tournament"
    await manager.connect(websocket, channel)
    
    try:
        # Отправляем начальные данные
        if tournament_type == "solo":
            data, total = get_solo_tournament_leaderboard(50)
            await manager.send_personal_message(websocket, {
                "type": "initial_data",
                "tournament": "solo",
                "data": {
                    "players": data,
                    "total_participants": total
                }
            })
        else:
            data, total = get_team_tournament_leaderboard(30)
            await manager.send_personal_message(websocket, {
                "type": "initial_data",
                "tournament": "team",
                "data": {
                    "teams": data,
                    "total_teams": total
                }
            })
        
        # Слушаем сообщения от клиента (для keep-alive)
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60  # Таймаут 60 секунд для keep-alive
                )
                
                # Обрабатываем ping
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Отправляем ping для проверки соединения
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, channel)


def notify_tournament_change(tournament_type: str, data: dict):
    """
    Функция для уведомления о изменениях в турнире.
    
    Вызывается из основного бота при завершении матча.
    
    Args:
        tournament_type: "solo" или "team"
        data: Данные обновления
    """
    channel = f"{tournament_type}_tournament"
    
    # Создаём task для асинхронной отправки
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(manager.broadcast(channel, {
            "type": "match_result",
            "tournament": tournament_type,
            "data": data
        }))
    except Exception:
        pass
