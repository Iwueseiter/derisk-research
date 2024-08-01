import asyncio
from decimal import Decimal
from typing import Iterable, Type

from db.crud import DBConnector
from db.models import LoanState

from handler_tools.constants import ProtocolIDs
from handlers.state import State, LoanEntity
from handlers.liquidable_debt.values import (LendingProtocolNames, COLLATERAL_FIELD_NAME,
                                             DEBT_FIELD_NAME, LIQUIDABLE_DEBT_FIELD_NAME, PRICE_FIELD_NAME)
from handlers.liquidable_debt.utils import Prices
from handlers.settings import TOKEN_PAIRS
from handlers.helpers import TokenValues, get_range, get_collateral_token_range


class BaseDBLiquidableDebtDataHandler:
    """
    A base handler that collects data from the DB,
    computes the liquidable debt and stores it in the database.

    :cvar AVAILABLE_PROTOCOLS: A list of all available protocols.
    """
    AVAILABLE_PROTOCOLS = [item.value for item in LendingProtocolNames]

    def __init__(self, *args, **kwargs):
        self.db_connector = DBConnector()

    @staticmethod
    def get_prices_range(collateral_token_name: str, current_price: Decimal) -> Iterable[Decimal]:
        """
        Get prices range based on the current price.
        :param current_price: Decimal - The current pair price.
        :param collateral_token_name: str - The name of the collateral token.
        :return: Iterable[Decimal] - The iterable prices range.
        """
        collateral_tokens = TOKEN_PAIRS.keys()

        if collateral_token_name in collateral_tokens:
            return get_collateral_token_range(collateral_token_name, current_price)

        return get_range(Decimal(0), current_price * Decimal("1.3"), Decimal(current_price / 100))

    def initialize_loan_entities(self, state: State, data: dict = None) -> State:
        """
        Initializes the loan entities in a state instance.
        :param state: State
        :param data: dict
        :return: State
        """
        for instance in data:
            loan_entity = self.loan_entity_class()

            loan_entity.debt = TokenValues(values=instance.debt)
            loan_entity.collateral = TokenValues(values=instance.collateral)

            state.loan_entities.update(
                {
                    instance.user: loan_entity,
                }
            )

        return state

    def fetch_data(self, protocol_name: ProtocolIDs | str) -> tuple:
        """
        Prepares the data for the given protocol.
        :param protocol_name: Protocol name.
        :return: tuple
        """
        loan_data = self.db_connector.get_loans(
            model=LoanState,
            protocol=protocol_name
        )
        interest_rate_models = self.db_connector.get_last_interest_rate_record_by_protocol_id(
            protocol_id=protocol_name
        )

        return loan_data, interest_rate_models


class ZkLendDBLiquidableDebtDataHandler(BaseDBLiquidableDebtDataHandler):
    """
    A zkLend handler that collects data from the DB,
    computes the liquidable debt and stores it in the database.

    :cvar AVAILABLE_PROTOCOLS: A list of all available protocols.
    """

    def __init__(
            self,
            loan_state_class: Type[State],
            loan_entity_class: Type[LoanEntity],
    ):
        super().__init__()
        self.state_class = loan_state_class
        self.loan_entity_class = loan_entity_class

    def calculate_liquidable_debt(self, protocol_name: str = None) -> list:
        """
        Calculates liquidable debt based on data provided and updates an existing data.
        Data to calculate liquidable debt for:
        :param protocol_name: str
        :return: A dictionary of the ready liquidable debt data.
        """
        data, interest_rate_models = self.fetch_data(protocol_name=protocol_name)
        state = self.state_class()
        state = self.initialize_loan_entities(state=state, data=data)

        # Set up collateral and debt interest rate models
        state.collateral_interest_rate_models = TokenValues(
            values=interest_rate_models.collateral
        )
        state.debt_interest_rate_models = TokenValues(
            values=interest_rate_models.debt
        )

        current_prices = Prices()
        asyncio.run(current_prices.get_lp_token_prices())

        hypothetical_collateral_token_prices = self.get_prices_range(
            collateral_token_name="STRK",
            current_price=current_prices.prices.values["STRK"]
        )

        result_data = list()
        # Go through first hypothetical prices and then through the debts
        for hypothetical_price in hypothetical_collateral_token_prices:
            liquidable_debt = state.compute_liquidable_debt_at_price(
                prices=TokenValues(values=current_prices.prices.values),
                collateral_token="STRK",
                collateral_token_price=hypothetical_price,
                debt_token="USDC",
            )

            if liquidable_debt > Decimal("0"):
                result_data.append({
                        LIQUIDABLE_DEBT_FIELD_NAME: liquidable_debt,
                        PRICE_FIELD_NAME: hypothetical_price,
                        COLLATERAL_FIELD_NAME: "STRK",
                        DEBT_FIELD_NAME: "USDC",
                    }
                )

        return result_data


class NostraAlphaDBLiquidableDebtDataHandler(BaseDBLiquidableDebtDataHandler):
    """
    A Nostra_alpha handler that collects data from the DB,
    computes the liquidable debt and stores it in the database.

    :cvar AVAILABLE_PROTOCOLS: A list of all available protocols.
    """

    def __init__(
            self,
            loan_state_class: Type[State],
            loan_entity_class: Type[LoanEntity],
    ):
        super().__init__()
        self.state_class = loan_state_class
        self.loan_entity_class = loan_entity_class

    def calculate_liquidable_debt(self, protocol_name: str = None) -> list:
        """
        Calculates liquidable debt based on data provided and updates an existing data.
        Data to calculate liquidable debt for:
        :param protocol_name: str
        :return: A dictionary of the ready liquidable debt data.
        """
        data, interest_rate_models = self.fetch_data(protocol_name=protocol_name)
        state = self.state_class()
        state = self.initialize_loan_entities(state=state, data=data)

        # Set up collateral and debt interest rate models
        state.collateral_interest_rate_models = TokenValues(
            values=interest_rate_models.collateral
        )
        state.debt_interest_rate_models = TokenValues(
            values=interest_rate_models.debt
        )

        current_prices = Prices()
        asyncio.run(current_prices.get_lp_token_prices())

        hypothetical_collateral_token_prices = self.get_prices_range(
            collateral_token_name="STRK",
            current_price=current_prices.prices.values["STRK"]
        )

        result_data = list()
        # Go through first hypothetical prices and then through the debts
        for hypothetical_price in hypothetical_collateral_token_prices:
            liquidable_debt = state.compute_liquidable_debt_at_price(
                prices=TokenValues(values=current_prices.prices.values),
                collateral_token="STRK",
                collateral_token_price=hypothetical_price,
                debt_token="USDC",
            )

            if liquidable_debt > Decimal("0"):
                result_data.append({
                        LIQUIDABLE_DEBT_FIELD_NAME: liquidable_debt,
                        PRICE_FIELD_NAME: hypothetical_price,
                        COLLATERAL_FIELD_NAME: "STRK",
                        DEBT_FIELD_NAME: "USDC",
                    }
                )

        return result_data


class NostraMainnetDBLiquidableDebtDataHandler(BaseDBLiquidableDebtDataHandler):
    """
    A Nostra_mainnet handler that collects data from the DB,
    computes the liquidable debt and stores it in the database.

    :cvar AVAILABLE_PROTOCOLS: A list of all available protocols.
    """

    def __init__(
            self,
            loan_state_class: Type[State],
            loan_entity_class: Type[LoanEntity],
    ):
        super().__init__()
        self.state_class = loan_state_class
        self.loan_entity_class = loan_entity_class

    def calculate_liquidable_debt(self, protocol_name: str = None) -> list:
        """
        Calculates liquidable debt based on data provided and updates an existing data.
        Data to calculate liquidable debt for:
        :param protocol_name: str
        :return: A dictionary of the ready liquidable debt data.
        """
        data, interest_rate_models = self.fetch_data(protocol_name=protocol_name)
        state = self.state_class()
        state = self.initialize_loan_entities(state=state, data=data)

        # Set up collateral and debt interest rate models
        state.collateral_interest_rate_models = TokenValues(
            values=interest_rate_models.collateral
        )
        state.debt_interest_rate_models = TokenValues(
            values=interest_rate_models.debt
        )

        current_prices = Prices()
        asyncio.run(current_prices.get_lp_token_prices())

        hypothetical_collateral_token_prices = self.get_prices_range(
            collateral_token_name="STRK",
            current_price=current_prices.prices.values["STRK"]
        )

        result_data = list()
        # Go through first hypothetical prices and then through the debts
        for hypothetical_price in hypothetical_collateral_token_prices:
            liquidable_debt = state.compute_liquidable_debt_at_price(
                prices=TokenValues(values=current_prices.prices.values),
                collateral_token="STRK",
                collateral_token_price=hypothetical_price,
                debt_token="USDC",
            )

            if liquidable_debt > Decimal("0"):
                result_data.append({
                        LIQUIDABLE_DEBT_FIELD_NAME: liquidable_debt,
                        PRICE_FIELD_NAME: hypothetical_price,
                        COLLATERAL_FIELD_NAME: "STRK",
                        DEBT_FIELD_NAME: "USDC",
                    }
                )

        return result_data
