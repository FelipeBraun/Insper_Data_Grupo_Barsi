"""Exporta leads filtrados para CSV pela linha de comando, sem abrir o app.

Usa as mesmas funções do app_sdr.py (filtros, contagem e exportação), sem alterá-lo.
O CSV sai idêntico ao do botão de exportação do app: separador ";" e UTF-8 com BOM.

"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import app_sdr  # só importa funções; não abre o app

PORTES_VALIDOS = sorted(app_sdr.PORTES)


def montar_filtros(args) -> dict:
    # Mesmo formato que o app guarda em st.session_state['aplicados'].
    return dict(
        setores=args.setor or [], ufs=[u.upper() for u in args.uf or []],
        cidades=[c.upper() for c in args.cidade or []], cnaes=args.cnae or [],
        portes=args.porte or [], busca=(args.busca or '').strip(), email=args.email,
        usar_capital=args.capital_min is not None or args.capital_max is not None,
        capital_min=float(args.capital_min or 0.0),
        capital_max=float(args.capital_max if args.capital_max is not None else 1_000_000.0),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Exporta leads filtrados para CSV.')
    parser.add_argument('--banco', type=Path, default=app_sdr.DATABASE,
                        help='Caminho do base_sdr_pronta.sqlite3 (padrão: pasta do projeto).')
    parser.add_argument('--uf', nargs='+', help='Estados, ex.: SP BA')
    parser.add_argument('--cidade', nargs='+', help='Municípios como no app, ex.: "SAO PAULO"')
    parser.add_argument('--setor', nargs='+', help='Setores como no app; veja --listar-setores')
    parser.add_argument('--cnae', nargs='+', help='Códigos CNAE de 7 dígitos, ex.: 6201501')
    parser.add_argument('--porte', nargs='+', choices=PORTES_VALIDOS,
                        help='00 não informado, 01 ME, 03 EPP, 05 demais')
    parser.add_argument('--email', action='store_true', help='Só empresas com e-mail')
    parser.add_argument('--busca', help='Texto ou CNPJ (mais lento)')
    parser.add_argument('--capital-min', type=float)
    parser.add_argument('--capital-max', type=float)
    parser.add_argument('--colunas', nargs='+', default=app_sdr.DEFAULT_COLUMNS,
                        help='Colunas do CSV (padrão: as mesmas do app)')
    parser.add_argument('--limite', type=int, help='Máximo de empresas (padrão: todas)')
    parser.add_argument('--pasta', type=Path,
                        help='Pasta de saída (padrão: exportacoes_sdr ao lado do banco)')
    parser.add_argument('--listar-setores', action='store_true', help='Mostra os setores e sai')
    args = parser.parse_args()

    if args.listar_setores:
        for nome in app_sdr.SETORES:
            print(nome)
        return 0

    banco = args.banco.expanduser().resolve()
    if not banco.is_file():
        parser.error(f'Banco não encontrado: {banco}')
    invalidas = [c for c in args.colunas if c not in app_sdr.EXPORT_COLUMNS]
    if invalidas:
        parser.error(f'Colunas desconhecidas: {invalidas}. Válidas: {app_sdr.EXPORT_COLUMNS}')
    setores_invalidos = [s for s in args.setor or [] if s not in app_sdr.SETOR_IDS]
    if setores_invalidos:
        parser.error(f'Setores desconhecidos: {setores_invalidos}. Use --listar-setores.')
    if args.limite is not None and args.limite < 1:
        parser.error('O limite precisa ser positivo.')
    if args.pasta:
        # O app lê esta variável para decidir onde salvar.
        import os
        os.environ['SDR_EXPORT_DIR'] = str(args.pasta.expanduser().resolve())

    catalogo = app_sdr.abrir_catalogo(banco)
    if catalogo.get('amostra_linhas'):
        print(f"Aviso: base de TESTE ({catalogo['amostra_linhas']:,} linhas).")
    filtros = montar_filtros(args)

    print('Contando empresas…', flush=True)
    total = app_sdr.contar_banco(banco, filtros)
    esperado = min(total, args.limite) if args.limite else total
    print(f'Encontradas: {app_sdr.numero_br(total)} · serão exportadas: {app_sdr.numero_br(esperado)}')
    if esperado == 0:
        print('Nada para exportar. Amplie os filtros.')
        return 1

    def progresso(n):
        print(f'\r  {app_sdr.numero_br(n)} de {app_sdr.numero_br(esperado)} gravadas', end='', flush=True)

    destino, gravadas = app_sdr.exportar_csv_hd(
        banco, filtros, args.colunas, catalogo['stats'], total, progresso,
        limite=args.limite, etapa=lambda texto: None)
    print(f'\nPRONTO: {app_sdr.numero_br(gravadas)} empresas em\n{destino}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(f'Não foi possível exportar: {exc}')
        